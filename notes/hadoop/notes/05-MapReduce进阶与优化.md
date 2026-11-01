# 05 MapReduce 进阶与优化

## 一句话

**MapReduce 跑得慢，九成原因在 Shuffle 和「某个 key 太多」**：倾斜、Join 方式、压缩、分区策略选对了能快几倍；只会加机器，往往没用。

## 钱花在哪：先看阶段代价

| 阶段 | 典型耗时占比 | 主要优化手段 |
| --- | --- | --- |
| Map 计算 | 10%–30% | 算法、JVM 重用、Combiner |
| Shuffle 网络 | **20%–50%** | 压缩、Combiner、倾斜治理 |
| Reduce 计算 | 10%–30% | 算法、并行度 |

Shuffle 数据量 ≈ map 输出条数 × 平均 (key,value) 大小。**从源头少发一条，比调十个参数都值**。

## 数据倾斜：最普遍的问题

**现象**：一批 reduce 早跑完，少数几个拖到最后；Job History 里各 reduce 的 Shuffle Bytes、Reduce Time 差一个数量级；task 计数器里某个 reduce 的 `REDUCE_INPUT_GROUPS` 远高于平均。

**根因**

- **null / 空 key**：所有空 key 都落到同一分区，全堆到一个 reduce。
- 少数大客户、大商家、默认值（`unknown`、`-1`）占了绝大部分记录。
- 时间字段天然集中：按 `2026-01` 汇总，所有 1 月的量都进同一个人。

## Join 的三种实现

| 方式 | 原理 | 适用条件 | 代价 |
| --- | --- | --- | --- |
| reduce-side join | 两表按 join key 输出，value 打 tag；reduce 里攒齐两边再拼 | 通用，两表都大 | 全部数据过 Shuffle |
| map-side join | 小表全量加载进每个 map 的内存，大表 split 流式匹配 | 小表能进内存（几十 MB 到数 GB） | 每个 map 重复加载小表 |
| semi-join | 先跑小 job 求小表的 key 集合，广播后大表先过滤，再走 reduce join | 小表 key 少、大表命中率低 | 多一个 job，但大表 Shuffle 大减 |
| Bloom Filter | semi-join 变体：用布隆过滤器代替完整 key 集合 | key 集合内存放不下 | 有假阳性，需二次校验 |

map-side join 用 DistributedCache 分发小表：

```java
import java.io.*;
import java.net.URI;
import java.util.*;
import org.apache.hadoop.fs.*;
import org.apache.hadoop.io.*;
import org.apache.hadoop.mapreduce.*;

public static class JoinMapper extends Mapper<LongWritable, Text, Text, Text> {
    private final Map<String, String> dim = new HashMap<String, String>();
    private final Text outKey = new Text();
    private final Text outVal = new Text();
    @Override
    protected void setup(Context context) throws IOException {
        URI[] files = context.getCacheFiles();
        if (files == null || files.length == 0) return;
        FileSystem fs = FileSystem.get(context.getConfiguration());
        BufferedReader br = new BufferedReader(new InputStreamReader(fs.open(new Path(files[0].getPath()))));
        String line;
        while ((line = br.readLine()) != null) {
            String[] parts = line.split("\t", 2);
            if (parts.length == 2) dim.put(parts[0], parts[1]);
        }
        br.close();
    }
    @Override
    protected void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        String[] parts = value.toString().split("\t");
        if (parts.length < 2) return;
        String name = dim.get(parts[0]);
        if (name == null) return;
        outKey.set(parts[0]);
        outVal.set(name + "\t" + parts[1]);
        context.write(outKey, outVal);
    }
}
```

提交时把小表放进缓存：`job.addCacheFile(new URI("hdfs:///dim/users.txt#users.txt"))`。

小表必须能装进单个 map 的 JVM 堆；map-side join 只能「大表 join 小表」；`getCacheFiles()` 返回带 `#别名` 的 URI，用 `getPath()` 取真实路径。

## 倾斜治理的四板斧

1. **空 key 随机打散**：`key = key == null || key.isEmpty() ? "null-" + rnd.nextInt(10) : key`；如果空 key 本身无意义，map 阶段直接过滤更好。
2. **加盐两阶段聚合**：热点 key 输出时拼随机前缀（`hot#0`…`hot#9`），第一个 job 局部汇总；第二个 job 去掉前缀再全局汇总。代价是多一个作业，收益是并行度从 1 变成 10。
3. **自定义 Partitioner**：已知热点（如某几个城市 ID）单独指定到空闲 reduce，其余按 hash。
4. **热点单独开小作业**：绝大多数数据走常规链路，剩下的大 key 用专门逻辑处理，互不拖累。

倾斜是单 key 级问题，加大 reduce 数通常治不了，还会多出一堆小文件。

## 压缩：压什么、在哪压

| 位置 | 配置 | 建议 |
| --- | --- | --- |
| Map 输出 | `mapreduce.map.output.compress=true` + Snappy | **几乎必开**，直接减少 Shuffle 网络 |
| Reduce 输出 | `mapreduce.output.fileoutputformat.compress=true` | 下游还要读就权衡 CPU |

- 压缩是 **CPU 换 IO/网络**。CPU 打满、磁盘和网络空闲时，压缩反而拖慢；不可切分的 Gzip/Snappy 大文件会被整份交给一个 map。

## 全排序：让多个 reduce 的输出全局有序

- 默认 HashPartitioner 只保证**每个分区内部有序**，分区之间无序。
- `TotalOrderPartitioner` 按 key 范围分区：partition 0 装最小一段，最后一段装最大的。
- 边界靠采样得到（`InputSampler.RandomSampler` 等），`InputSampler.writePartitionFile` 写完会自动加入 DistributedCache；采样要扫数据，分布剧变时边界会不准。

用法两行：`job.setPartitionerClass(TotalOrderPartitioner.class)`，再用 `InputSampler.writePartitionFile(job, sampler)` 写分区文件。

## 二次排序：按 A 分组、按 B 排序

需求：每年取温度最高的前 3 条。做法是把 `(year, temp)` 组成复合 key，**排序比较器用整个复合 key，分组比较器只用 year**。

```java
public static class YearTemp implements WritableComparable<YearTemp> {
    private int year;
    private int temp;
    public int getYear() { return year; }
    public void set(int y, int t) { year = y; temp = t; }
    @Override
    public void write(DataOutput out) throws IOException { out.writeInt(year); out.writeInt(temp); }
    @Override
    public void readFields(DataInput in) throws IOException { year = in.readInt(); temp = in.readInt(); }
    @Override
    public int compareTo(YearTemp o) {
        int c = Integer.compare(year, o.year);
        return c != 0 ? c : Integer.compare(temp, o.temp);
    }
}
public static class YearGroupingComparator extends WritableComparator {
    protected YearGroupingComparator() { super(YearTemp.class, true); }
    @Override
    public int compare(WritableComparable a, WritableComparable b) {
        return Integer.compare(((YearTemp) a).getYear(), ((YearTemp) b).getYear());
    }
}
```

作业里 `job.setGroupingComparatorClass(YearGroupingComparator.class)`；排序则用复合 key 的 `compareTo`。

- 复合 key 到达 reduce 已按 (year, temp) 升序；分组只认 year，一次 `reduce()` 拿到一年全部记录，遍历时天然有序。
- 本质是**排序键 ≠ 分组键**；只改 key 不改分组，等于普通排序。

## MultipleOutputs 与计数器

- `MultipleOutputs` 让一个 reduce 按业务写多个目录/文件，避免下游再拆一遍。
- 用法：`setup` 里 `mos = new MultipleOutputs<Text, IntWritable>(context)`；输出 `mos.write("hotwords", key, value)`；`cleanup` 里 `mos.close()`。
- 每个 output name 对应 `FileOutputFormat.setOutputPath` 下的一个子目录，文件名沿用 `part-r-xxxxx`。
- 计数器做数据质量监控：`context.getCounter("quality", "bad_rows").increment(1)`，作业结束后读 `job.getCounters().findCounter("quality", "bad_rows").getValue()`；丢弃了多少行、null key 多少条，比事后翻日志快。

## 常用调优参数

| 参数 | 默认 | 作用 |
| --- | --- | --- |
| `mapreduce.input.fileinputformat.split.maxsize` | `Long.MAX_VALUE` | 限制 split 上限；调小→更多 map，调大→更少 map |
| `mapreduce.input.fileinputformat.split.minsize` | `1` | 与 block 大小共同决定 split，配合 `CombineTextInputFormat` 治小文件 |
| `mapreduce.task.io.sort.mb` | `100` | 环形缓冲区大小；map 输出多就加到 200–400 |
| `mapreduce.map.sort.spill.percent` | `0.80` | 溢写阈值；调高减少 spill 次数，但更吃内存 |
| `mapreduce.task.io.sort.factor` | `10` | 归并路数；调大减少 merge 轮数，受文件句柄限制 |
| `mapreduce.job.reduce.slowstart.completedmaps` | `0.05` | map 完成多少比例开始调度 reduce |
| `mapreduce.reduce.shuffle.parallelcopies` | `5` | reduce 并行拉取数；网络好可到 10 |
| `mapreduce.job.jvm.numtasks` | `1` | 每个 JVM 跑几个 task；小任务多调到 10–20 省启动开销 |

## 反模式清单

- reduce 数只设 1，一个大 reducer 扛全量数据。
- 在 mapper 里逐条查数据库（N+1 查询），把分布式计算变成串行等 IO。
- 两张大表硬做 map-side join，直接 OOM 或频繁 GC。
- Combiner 里做非结合操作（求平均、去重），结果悄悄错。

## 什么时候该换 Spark / Tez

| 场景 | 建议 |
| --- | --- |
| 多阶段 DAG、迭代、SQL 分析 | Spark（内存 + 血统容错） |
| 单 job 巨大但阶段简单，已有稳定脚本 | 保留 MapReduce，风险最低 |
| 多 job 串联、想少落盘 | Tez 或 Spark，DAG 合并 |
| 流式 / 亚秒级 | Flink、Spark Streaming |

MapReduce 没有被淘汰，它的价值是**极稳、极省、对超大规模一次性批处理友好**。新业务用 Spark，存量链路继续跑 MR，是很常见的组合。

## 自测

1. 怎么判断一个作业存在数据倾斜？请给出两个可观察到的证据。
2. reduce-side join 和 map-side join 各适合什么条件？semi-join 比它们多省了什么？
3. 全排序为什么不能直接用默认 HashPartitioner？`TotalOrderPartitioner` 依赖什么才能切出正确边界？

## 参考与官方文档

- [MapReduce Tutorial](https://hadoop.apache.org/docs/stable/hadoop-mapreduce-client/hadoop-mapreduce-client-core/MapReduceTutorial.html)
- [MapReduce 默认配置（mapred-default.xml）](https://hadoop.apache.org/docs/stable/hadoop-mapreduce-client/hadoop-mapreduce-client-core/mapred-default.xml)
- [TotalOrderPartitioner API](https://hadoop.apache.org/docs/r3.3.6/api/org/apache/hadoop/mapreduce/lib/partition/TotalOrderPartitioner.html)
- [InputSampler API](https://hadoop.apache.org/docs/r3.3.6/api/org/apache/hadoop/mapreduce/lib/partition/InputSampler.html)
- [Hadoop: The Definitive Guide（第 9 章 作业调优）](https://www.oreilly.com/library/view/hadoop-the-definitive/9781491901687/)
