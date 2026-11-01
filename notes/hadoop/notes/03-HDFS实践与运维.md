# 03 HDFS 实践与运维

## 一句话

**会用 `hdfs dfs` 只是起点**：真正的 HDFS 能力在「看懂 fsck/dfsadmin 的输出、算得清小文件账单、扩得了容、退得了役、排得了错」。

## 命令速查

三个入口别混：`hdfs dfs` 是文件系统用户命令；`hdfs dfsadmin` 是集群管理；`hdfs fsck` 是一致性检查。

| 目的 | 命令 | 说明 |
| --- | --- | --- |
| 列目录 | `hdfs dfs -ls -R /data` | `-R` 递归 |
| 建目录 | `hdfs dfs -mkdir -p /data/dt=2026-11-01` | 支持多级 |
| 上传/下载 | `hdfs dfs -put local /data/`；`hdfs dfs -get /data/f local` | 也可用 copyFromLocal/copyToLocal |
| 查看 | `hdfs dfs -cat /data/f`；`hdfs dfs -text /data/f` | `-text` 可解压 SequenceFile/压缩；大文件别 cat |
| 复制/移动 | `hdfs dfs -cp /a /b`；`hdfs dfs -mv /a /b` | mv 只改元数据，很快 |
| 删除 | `hdfs dfs -rm -r /data/old`；`hdfs dfs -rm -skipTrash /data/old` | 默认进回收站 |
| 容量 | `hdfs dfs -du -s -h /data`；`hdfs dfs -df -h` | du 是文件实际大小，df 是集群容量 |
| 统计 | `hdfs dfs -count -q /data` | 目录数/文件数/总大小/配额 |
| 校验和 | `hdfs dfs -checksum /data/f` | 返回 MD5-of-CRC，可用于比对 |
| 权限 | `hdfs dfs -chmod -R 755 /data`；`hdfs dfs -chown -R u:g /data` | 与 Linux 类似 |
| 副本数 | `hdfs dfs -setrep -w 2 /data/f` | `-w` 等待副本完成 |
| 看配置 | `hdfs dfs -getconf -confKey dfs.blocksize` | 查当前生效值 |
| 回收站 | `hdfs dfs -expunge`；`hdfs dfs -expunge -immediate` | 立即清空回收站 |
| 集群报告 | `hdfs dfsadmin -report` | 容量、DN 状态、副本情况 |
| 安全模式 | `hdfs dfsadmin -safemode get/enter/leave/wait` | 维护时手动进入 |
| 刷新节点 | `hdfs dfsadmin -refreshNodes` | 扩缩容后必做 |
| 快照开关 | `hdfs dfsadmin -allowSnapshot /data` | 之后才能 createSnapshot |
| 均衡带宽 | `hdfs dfsadmin -setBalancerBandwidth 104857600` | 字节/秒 |
| 一致性检查 | `hdfs fsck /data -files -blocks -locations` | 看缺块/坏块/副本 |
| 坏块清单 | `hdfs fsck / -list-corruptfileblocks` | 全集群扫，代价高 |
| 打开中文件 | `hdfs fsck /data -openforwrite` | 查泄漏的写租约 |

## Java API 最小示例

```java
import java.io.IOException;
import java.net.URI;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.*;

public class HdfsDemo {
    public static void main(String[] args) throws Exception {
        Configuration conf = new Configuration();
        conf.set("fs.defaultFS", "hdfs://localhost:9000");
        FileSystem fs = FileSystem.get(URI.create("hdfs://localhost:9000"), conf, "hadoop");
        Path file = new Path("/tmp/demo.txt");

        try (FSDataOutputStream out = fs.create(file, true)) {
            out.write("hello hdfs\n".getBytes("UTF-8"));
        }
        try (FSDataInputStream in = fs.open(file)) {
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) > 0) {
                System.out.write(buf, 0, n);
            }
        }
        FileStatus[] list = fs.listStatus(new Path("/tmp"));
        for (FileStatus s : list) {
            System.out.println(s.getPath() + "\t" + s.getLen() + "\t" + s.getReplication());
        }
        fs.close();
    }
}
```

编译运行（Java 8 语法，无 `var`、无 `List.of`）：

```bash
javac -cp "$(hadoop classpath)" HdfsDemo.java
java -cp ".:$(hadoop classpath)" HdfsDemo
```

要点：`FileSystem.get(URI, conf, user)` 显式传用户；用完 `close()`；`create(path, true)` 的 `true` 是覆盖；读大文件要循环读，不要一次 `readAllBytes`。

## WebHDFS / HttpFS / Python

- **WebHDFS**：NameNode 内置 REST 接口，HTTP 端口 9870（HTTPS 9871），DataNode 9864。元数据操作走 NN，真正的读写会 307 重定向到 DataNode。
- **HttpFS**：独立网关服务（默认端口 14000），适合跨防火墙/多集群代理；功能与 WebHDFS 类似。

```bash
curl -s "http://nn:9870/webhdfs/v1/tmp?op=LISTSTATUS"
curl -s -L -X PUT -T hello.txt "http://nn:9870/webhdfs/v1/tmp/hello.txt?op=CREATE&overwrite=true"
curl -s -L "http://nn:9870/webhdfs/v1/tmp/hello.txt?op=OPEN"
```

`op=CREATE` 必须加 `-L` 跟随重定向；`op=MKDIRS` 用 PUT；`op=GETFILESTATUS` 返回 JSON。

## 关键配置项

| 配置 | 默认 | 作用与建议 |
| --- | --- | --- |
| `dfs.blocksize` | 128MB | 大文件块大小；小文件多时别乱调大 |
| `dfs.replication` | 3 | 副本数；冷数据可降为 2 或改用 EC |
| `dfs.namenode.handler.count` | 10 | NN RPC 线程数；高并发建文件/删文件时调大 |
| `dfs.datanode.max.transfer.threads` | 4096 | DN 数据传输线程上限；高并发读时调大 |
| `dfs.datanode.du.reserved` | 0 | 每块盘为系统预留的空间，生产必须设（如 10–20GB） |
| `dfs.namenode.checkpoint.period` | 3600 秒 | SNN/Standby 的 checkpoint 周期 |
| `dfs.namenode.checkpoint.txns` | 1000000 | 累计事务数达到就触发 checkpoint |
| `dfs.client-write-packet-size` | 65536 | 写 packet 大小；高延迟网络可调到 128KB |
| `fs.trash.interval` | 0（关闭） | 回收站保留分钟数，生产常设 1440 |

## 小文件问题

先算账：1 亿个 10KB 的小文件，总数据只有 1TB，但——

- NameNode 要记 1 亿个 INode、约 1 亿个块、3 亿个副本位置，按 150B/对象估，**堆内存 15–20GB**。
- 每个文件至少占 1 个块（哪怕只有 10KB），块数爆炸。
- 用 `FileInputFormat` 时**每个文件至少一个 map task**，1 亿文件就是 1 亿个 task，调度开销远超计算本身。
- 每个文件 open/close 都是 RPC，几亿次 RPC 会把 NN 打满；DN 上大量小 block 也会让磁盘随机 IO 变差。

治理手段（按优先级）：

| 手段 | 做法 | 注意 |
| --- | --- | --- |
| 上游合并 | Flume 调大 `hdfs.rollSize`/`hdfs.rollInterval`，Kafka→HDFS 按批写 | 最有效，别让文件碎着落盘 |
| 计算端合并 | `CombineTextInputFormat`/`CombineFileInputFormat` 把小文件合成一个 split | 只解决 map 数，不解决 NN 内存 |
| 列式/容器格式 | Parquet/ORC 把多行放一个文件；SequenceFile 合并小文件 | 顺便压缩，提高扫描效率 |
| 归档 HAR | `hadoop archive -archiveName logs.har -p /src /dest` | 读要 `har://`；索引仍占空间 |
| 定期合并任务 | 按目录/大小阈值批量读→写大文件→校验行数/校验和→原子 rename→删原文件 | 要防重跑与并发写 |
| 分区治理 | Hive 按天分区而不是按小时/分钟；控制 reduce 数与分桶 | 分区目录本身也是小文件 |

## 扩容、退役与均衡

- **白名单/黑名单**：`dfs.hosts`（include，只允许列表内 DN 接入）、`dfs.hosts.exclude`（exclude，列表内 DN 进入退役）。改完必须 `hdfs dfsadmin -refreshNodes`。
- **退役不是立刻关机**：NN 会先把该节点上的副本迁走，达到副本要求后才变 `Decommissioned`；期间节点仍在服务读。用 `hdfs dfsadmin -report` 或 NN UI 看 `Decommissioning`。
- **Balancer**：`hdfs balancer -threshold 10`（阈值 10%），低峰期跑；可加 `-include`/`-exclude` 限定范围。带宽用 `hdfs dfsadmin -setBalancerBandwidth <bytes/s>` 限制。
- **Mover**：EC 或存储策略场景下移动块用 `hdfs mover -p /cold`。
- **磁盘故障**：`dfs.datanode.failed.volumes.tolerated` 默认 0，一块盘坏 DataNode 就停；生产可设 1–2。`dfs.datanode.data.dir` 配多块盘可分散 IO。换盘后通常重启 DN；部分 3.x 版本支持卷刷新命令，以所用发行版文档为准。
- **扩容顺序**：新节点写入 include → `refreshNodes` → 确认 DN 注册 → `balancer`；机架感知依赖 topology script 或节点组配置。

## 安全模式、快照、回收站、ACL、加密实操

```bash
# 安全模式
hdfs dfsadmin -safemode get
hdfs dfsadmin -safemode enter
hdfs dfsadmin -safemode wait
hdfs dfsadmin -safemode leave

# 快照（目录必须先 allowSnapshot）
hdfs dfsadmin -allowSnapshot /data
hdfs dfs -createSnapshot /data s1
hdfs dfs -ls /data/.snapshot/s1
hdfs snapshotDiff /data s1 s2

# 回收站
hdfs dfs -rm -r /data/old          # 默认进 /user/<u>/.Trash/Current
hdfs dfs -expunge -immediate

# ACL
hdfs dfs -setfacl -m user:alice:rwx /data/report
hdfs dfs -getfacl /data/report
hdfs dfs -setfacl -b /data/report

# 透明加密（需先配好 KMS）
hadoop key create mykey
hdfs crypto -createZone -keyName mykey -path /secure
hdfs crypto -listZones
```

注意：`-safemode leave` 不是万能药，先看 `report` 里缺块/副本是否达标；快照是只读视图，恢复靠从 `.snapshot/s1` 拷回；ACL 的 `-b` 是清空所有 ACL。

## 常见报错与处理

| 报错/现象 | 常见原因 | 处理 |
| --- | --- | --- |
| `Missing blocks` / `CORRUPT block` | DN 下线、磁盘损坏、副本不足 | `hdfs fsck / -list-corruptfileblocks`；等副本重建；确认不可恢复再 `-delete` |
| `Could not obtain block: BP-...` | 所有副本所在 DN 不可达、网络/防火墙、权限 | 查 DN 心跳与 `fsck -locations`，排查网络 |
| `Slow BlockReceiver write packet to disk` | 磁盘慢、坏道、IO 饱和 | `iostat` 定位盘，换盘或降写入压力 |
| `LeaseExpiredException` | 客户端写一半崩溃/超时，租约没释放 | `hdfs debug recoverLease -path /f -retries 3` |
| `SafeModeException: Cannot create file` | NN 在安全模式 | `-safemode get/wait`；确认块报告达标再 leave |
| `NameNode is not formatted` / `Incompatible clusterIDs` | 没 format，或重复 format 后 DN 目录残留 | 清空 DN 的 data 目录再启动（生产谨慎） |
| `could only be replicated to 0 nodes` | 磁盘满、reserved 过大、DN 全忙、副本数大于节点数 | 查 `df`、`du.reserved`、DN 数量 |
| `Too many open files` / `No space left on device` | ulimit 太小 / 磁盘满 | 调大 nofile；清数据、加盘、调 reserved |

## 自测

1. `hdfs dfs -du` 和 `hdfs dfs -df` 分别统计什么？排查「磁盘写满」该看哪个？
2. 1 亿个 10KB 小文件大约吃掉多少 NN 堆？为什么用 CombineTextInputFormat 不能根治？
3. 节点退役时执行 `refreshNodes` 之后，为什么不能马上关机？怎么确认退役完成？

## 参考与官方文档

- [HDFS Commands Guide](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HDFSCommands.html)
- [HDFS 默认配置项](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/hdfs-default.xml)
- [WebHDFS REST API](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/WebHDFS.html)
- [Hadoop FileSystem API](https://hadoop.apache.org/docs/stable/api/org/apache/hadoop/fs/FileSystem.html)
