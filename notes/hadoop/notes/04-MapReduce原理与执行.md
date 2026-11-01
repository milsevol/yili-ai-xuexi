# 04 MapReduce 原理与执行

## 一句话

**MapReduce = 「分而治之 + 按 key 归并」的批处理模型**：Map 把数据分片并行处理，Shuffle 把同 key 的数据拉到一起，Reduce 做汇总；切分、调度、容错由框架负责，你只写 map/reduce 两个函数。

## 编程模型：一条流水线

```
InputFormat → Split → RecordReader → Mapper → Partitioner → Sort/Group → Reducer → OutputFormat
```

| 阶段 | 谁来做 | 干什么 | 可自定义 |
| --- | --- | --- | --- |
| InputFormat | 框架 | 决定文件怎么切成 split、怎么读成 K/V | 是 |
| Mapper | 你 | 每条记录输出若干 (key, value) | 是 |
| Partitioner | 框架/你 | 决定 key 去哪个 reduce | 是 |
| Sort/Group | 框架 | map 输出按 key 排序；分组决定一次 reduce 调用处理哪些 key | 比较器可自定义 |
| Reducer | 你 | 每个 key 组调用一次，输出结果 | 是 |
| OutputFormat | 框架 | 决定结果怎么写（文本、SequenceFile、数据库） | 是 |

## 为什么一定要 Shuffle

Map 输出留在本地，同一 key 散落在多个 map 中；Reduce 要看到某 key 的全部 value，就必须**按 key 重新分发**——这就是 Shuffle：

```
Map 1/2/3 ── 按 key hash 分桶 ──► 本地磁盘 ──► Reduce N 拉取自己的 partition
```

Shuffle 是磁盘写、网络传输、排序合并的集中地，也是 MapReduce 优化的主战场。

## Split 与 Block 的关系

- **Block 是存储单位**（HDFS 按 128MB 切），**Split 是计算单位**（InputFormat 切）；split 是逻辑切分，不复制数据，通常对应一个 block，也可跨 block。
- 大小公式 `max(minSize, min(maxSize, blockSize))`：minsize 默认 1 字节，maxsize 默认 `Long.MAX_VALUE`。
- 例：260MB 文件、128MB block → 3 个 split（128+128+4）；maxsize 设 64MB → 5 个 split（64×4+4）。
- 默认切分对齐 block 以保证**数据本地性**；`CombineTextInputFormat` 可把小文件合进一个 split，减少 map 数。

## 完整执行链路

```
Client → RM（提交/分配）→ NM 启动 MRAppMaster（算 split、申请 container、监控）
Map：RecordReader → map() → 环形缓冲(100MB/80%) → spill → merge
Reduce：copy(HTTP 拉取) → merge → sort/group → reduce() → OutputFormat
```

1. **submit**：客户端 `waitForCompletion()` 触发提交：上传 jar、配置、split 元数据到 HDFS 的 staging 目录，向 RM 申请 application。
2. **启动 AM**：RM 分配一个 Container，NodeManager 启动 `MRAppMaster`（默认 1536MB）。
3. **初始化**：AM 读取 split 信息，确定 map/reduce task 数，向 RM 持续申请资源。
4. **Map**：每个 map task 读一个 split，`map()` 的输出先写**环形缓冲区**（默认 100MB，`mapreduce.task.io.sort.mb`）。
5. **Spill**：缓冲区到 **80%**（`mapreduce.map.sort.spill.percent`）触发溢写：按 partition + key 排序，可选 combiner，写到本地磁盘。
6. **Merge**：多次 spill 后归并（`mapreduce.task.io.sort.factor` 默认 10 路），最终每个 partition 一个大文件。
7. **Reduce 启动**：`mapreduce.job.reduce.slowstart.completedmaps` 默认 **0.05**，5% 的 map 完成就可以开始申请 reduce，边 map 边 shuffle。
8. **Shuffle**：reduce 通过 HTTP 从各 map 节点拉取属于自己的 partition，并行度由 `mapreduce.reduce.shuffle.parallelcopies` 默认 **5** 控制。
9. **Merge/Sort/Reduce/Commit**：拉来的数据归并、按 key 排序、分组调用 `reduce()`；OutputFormat 写出结果，OutputCommitter 写 `_SUCCESS` 并清理临时目录。

## 环形缓冲区、Spill、Combiner

- 环形缓冲区默认 **100MB**，其中一部分存序列化元数据；到 80% 软阈值后在后台 spill，spill 期间采集不阻塞，所以实际 spill 可能超过 80%。
- 每次 spill 都按 **partition 编号 → key** 排序，并生成索引；reduce 才能按 partition 精准拉取。
- **Combiner 是 map 端的「迷你 reducer」**，在 spill 前对同 key 做一次预聚合，显著减少写盘和网络数据。
- Combiner 的适用条件：
  - 操作满足**结合律和交换律**（sum、max、min、count）。
  - 不改变最终语义；求平均值不能直接当 combiner，要改成「sum + count」再相除。
  - 输入/输出类型必须与 reducer 的输入类型一致（`K,V → K,V`）。
- Combiner 可能执行 **0 次、1 次或多次**，框架不保证；不能依赖它做正确性。

## Partitioner、排序与分组

- 默认 **HashPartitioner**：`(key.hashCode() & Integer.MAX_VALUE) % numReduceTasks`；`mapreduce.job.reduces` 默认 **1**，所有 key 进同一 reducer，Partitioner 实际不起作用。
- 自定义 Partitioner：实现 `Partitioner<K,V>` 的 `getPartition()`，再 `job.setPartitionerClass(...)`。
- **排序比较器**：map 输出按 key 排序，默认用 key 的 `compareTo`；可 `job.setSortComparatorClass(...)`。
- **分组比较器**：决定哪些相邻 key 算同一组、进入同一次 `reduce()`；可 `job.setGroupingComparatorClass(...)`。二次排序就靠它（第 05 章）。

## WordCount 完整代码（Java 8）

```java
import java.io.IOException;
import java.util.StringTokenizer;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.*;
import org.apache.hadoop.mapreduce.*;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;

public class WordCount {
    public static class TokenizerMapper extends Mapper<Object, Text, Text, IntWritable> {
        private static final IntWritable ONE = new IntWritable(1);
        private final Text word = new Text();
        @Override
        public void map(Object key, Text value, Context context) throws IOException, InterruptedException {
            StringTokenizer itr = new StringTokenizer(value.toString());
            while (itr.hasMoreTokens()) {
                word.set(itr.nextToken());
                context.write(word, ONE);
            }
        }
    }
    public static class IntSumReducer extends Reducer<Text, IntWritable, Text, IntWritable> {
        private final IntWritable result = new IntWritable();
        @Override
        public void reduce(Text key, Iterable<IntWritable> values, Context context) throws IOException, InterruptedException {
            int sum = 0;
            for (IntWritable val : values) {
                sum += val.get();
            }
            result.set(sum);
            context.write(key, result);
        }
    }
    public static void main(String[] args) throws Exception {
        Configuration conf = new Configuration();
        Job job = Job.getInstance(conf, "word count");
        job.setJarByClass(WordCount.class);
        job.setMapperClass(TokenizerMapper.class);
        job.setCombinerClass(IntSumReducer.class);
        job.setReducerClass(IntSumReducer.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(IntWritable.class);
        job.setNumReduceTasks(2);
        FileInputFormat.addInputPath(job, new Path(args[0]));
        FileOutputFormat.setOutputPath(job, new Path(args[1]));
        System.exit(job.waitForCompletion(true) ? 0 : 1);
    }
}
```

```bash
javac -cp "$(hadoop classpath)" WordCount.java && jar cf wc.jar WordCount*.class
hadoop jar wc.jar WordCount /input /output
```

```bash
hdfs dfs -cat /input/* | tr ' ' '\n' | grep -v '^$' | sort | uniq -c | sort -rn
```

## 常用 InputFormat / OutputFormat

| 类型 | 说明 |
| --- | --- |
| `TextInputFormat` | 默认；按行读，key 是行偏移（LongWritable），value 是整行（Text） |
| `KeyValueTextInputFormat` | 按分隔符（默认 tab）拆成 key/value |
| `CombineTextInputFormat` | 合并小文件，减少 map 数 |
| `SequenceFileInputFormat` | 读二进制 K/V 文件 |
| `TextOutputFormat` | 默认；`key \t value` 文本输出 |
| `SequenceFileOutputFormat` | 二进制输出，适合作为下游输入 |

## 压缩：Codec 选择

| Codec | 可切分 | 压缩比 | 速度 | 典型用途 |
| --- | --- | --- | --- | --- |
| Gzip | **否** | 高 | 中 | 冷数据归档、最终输出 |
| Bzip2 | **是** | 很高 | 慢 | 归档，CPU 换空间 |
| LZO | 有索引才可切分 | 中 | 快 | 大文件中间结果，需额外配置 |
| Snappy | **否** | 中 | 最快 | map 输出、Shuffle 中间数据 |
| Zstd | **否**（默认容器） | 高 | 快 | 3.x 新选项，中间/最终输出 |

- Map 输出压缩：`mapreduce.map.output.compress=true`，codec 如 `org.apache.hadoop.io.compress.SnappyCodec`，减少 Shuffle 网络量。
- 最终输出压缩：`mapreduce.output.fileoutputformat.compress=true`，再配 `.codec` 和 `.type`（SequenceFile 用 `BLOCK`）。

## Counters、推测执行、重试、JVM 重用、Uber

- **Counter**：`context.getCounter("mygroup", "bad_rows").increment(1)`；作业结束用 `job.getCounters()` 读。内置计数器包括 `MAP_INPUT_RECORDS`、`REDUCE_INPUT_RECORDS`、`REDUCE_INPUT_GROUPS`、`COMBINE_INPUT_RECORDS` 等。
- 命令行查计数器：`mapred job -counter <jobid> <group> <name>`。
- **推测执行**：`mapreduce.map.speculative`/`reduce.speculative` 默认 **true**；某个 task 明显慢于平均（默认慢 1 个标准差）就启动备份，谁先完成用谁。集群资源紧张时可关掉。
- **重试**：`mapreduce.map.maxattempts`/`reduce.maxattempts` 默认 **4**；`mapreduce.task.timeout` 默认 **600000ms（10 分钟）**，10 分钟无进展会被 kill 重试。
- **JVM 重用与 Uber**：`mapreduce.job.jvm.numtasks` 默认 **1**（一 task 一 JVM），小任务多可调大但要防内存泄漏；`mapreduce.job.ubertask.enable` 默认 **false**，开启后小作业（≤9 map、≤1 reduce）直接在 AM 的 JVM 里串行跑。

## MapReduce 的局限（和 Spark 对比）

| 维度 | MapReduce | Spark |
| --- | --- | --- |
| 执行模型 | 固定 Map → Reduce 两段，多步要串联多个 job | 任意 DAG，一个 job 内多 stage |
| 中间数据 | 落 HDFS/本地磁盘 | 尽量内存，放不下才 spill |
| 迭代计算 | 每轮都读写 HDFS，慢 | cache/persist，快一个数量级 |
| 交互式/流/容错 | 不支持交互与流；task 级重试 | SQL、Streaming、血统容错都支持 |
| 适合 | 一次性超大规模批处理、极稳的离线链路 | 迭代、SQL、ML、流、复杂 DAG |

## 自测

1. Split 和 Block 是什么关系？260MB 文件、128MB block，默认会切几个 split？
2. 环形缓冲区默认多大、到多少触发 spill？spill 时按什么排序？
3. Combiner 能不能用来算平均值？为什么？它一定会执行吗？

## 参考与官方文档

- [MapReduce Tutorial](https://hadoop.apache.org/docs/stable/hadoop-mapreduce-client/hadoop-mapreduce-client-core/MapReduceTutorial.html)
- [MapReduce 默认配置（mapred-default.xml）](https://hadoop.apache.org/docs/stable/hadoop-mapreduce-client/hadoop-mapreduce-client-core/mapred-default.xml)
- [Hadoop: The Definitive Guide（第 2 章 MapReduce）](https://www.oreilly.com/library/view/hadoop-the-definitive/9781491901687/)
