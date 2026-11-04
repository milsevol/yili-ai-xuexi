import { defineConfig } from 'vitepress'

// 本地开发默认 '/'；GitHub Pages / 打包脚本用 '/yili-ai-xuexi/'
// 可被环境变量 VITEPRESS_BASE 覆盖，例如：VITEPRESS_BASE=/yili-ai-xuexi/
const defaultBase = process.env.GITHUB_ACTIONS ? '/yili-ai-xuexi/' : '/'
const base = process.env.VITEPRESS_BASE || defaultBase

export default defineConfig({
  title: 'yili-ai-xuexi',
  description: '个人技术知识学习仓库：大数据、AI、量化交易 — 笔记 + Python 演示',
  lang: 'zh-CN',
  base,
  cleanUrls: true,
  lastUpdated: true,

  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: 'Hadoop', link: '/hadoop/' },
      { text: 'Hive', link: '/hive/' },
      { text: 'Spark', link: '/spark/' },
      { text: 'Flink', link: '/flink/' },
      { text: 'Kafka', link: '/kafka/' },
      { text: '湖仓一体', link: '/iceberg/' },
      { text: 'HBase', link: '/hbase/' },
      { text: 'ClickHouse', link: '/clickhouse/' },
      { text: '海豚调度', link: '/dolphin-scheduler/' },
    ],

    sidebar: {
      '/hadoop/': [
        {
          text: 'Hadoop',
          items: [
            { text: '主题入口', link: '/hadoop/' },
            { text: '01 概述与定位', link: '/hadoop/notes/01-概述与定位' },
            { text: '02 HDFS 架构与原理', link: '/hadoop/notes/02-HDFS架构与原理' },
            { text: '03 HDFS 实践与运维', link: '/hadoop/notes/03-HDFS实践与运维' },
            { text: '04 MapReduce 原理与执行', link: '/hadoop/notes/04-MapReduce原理与执行' },
            { text: '05 MapReduce 进阶与优化', link: '/hadoop/notes/05-MapReduce进阶与优化' },
            { text: '06 YARN 资源管理与调度', link: '/hadoop/notes/06-YARN资源管理与调度' },
            { text: '07 Hadoop 生态组件', link: '/hadoop/notes/07-Hadoop生态组件' },
            { text: '08 部署与集群规划', link: '/hadoop/notes/08-部署与集群规划' },
            { text: '09 运维监控与故障排查', link: '/hadoop/notes/09-运维监控与故障排查' },
            { text: '10 生态对比与 FAQ', link: '/hadoop/notes/10-生态对比与FAQ' },
          ],
        },
      ],
      '/hive/': [
        {
          text: 'Hive',
          items: [
            { text: '主题入口', link: '/hive/' },
            { text: '01 概述与定位', link: '/hive/notes/01-概述与定位' },
            { text: '02 架构与核心组件', link: '/hive/notes/02-架构与核心组件' },
            { text: '03 数据模型与存储格式', link: '/hive/notes/03-数据模型与存储格式' },
            { text: '04 SQL 与分区管理', link: '/hive/notes/04-SQL与分区管理' },
            { text: '05 数仓分层设计', link: '/hive/notes/05-数仓分层设计' },
            { text: '06 执行引擎与 Tez/Spark 切换', link: '/hive/notes/06-执行引擎与TezSpark切换' },
            { text: '07 性能调优', link: '/hive/notes/07-性能调优' },
            { text: '08 ACID 与事务', link: '/hive/notes/08-ACID与事务' },
            { text: '09 Hive 与周边组件', link: '/hive/notes/09-Hive与周边组件' },
            { text: '10 生态对比与 FAQ', link: '/hive/notes/10-生态对比与FAQ' },
          ],
        },
      ],
      '/spark/': [
        {
          text: 'Spark',
          items: [
            { text: '主题入口', link: '/spark/' },
            { text: '01 概述与定位', link: '/spark/notes/01-概述与定位' },
            { text: '02 架构与运行原理', link: '/spark/notes/02-架构与运行原理' },
            { text: '03 RDD 核心抽象', link: '/spark/notes/03-RDD核心抽象' },
            { text: '04 DataFrame 与 Dataset', link: '/spark/notes/04-DataFrame与Dataset' },
            { text: '05 Spark SQL 与 Catalyst', link: '/spark/notes/05-SparkSQL与Catalyst' },
            { text: '06 Shuffle 与执行计划', link: '/spark/notes/06-Shuffle与执行计划' },
            { text: '07 部署与资源配置', link: '/spark/notes/07-部署与资源配置' },
            { text: '08 性能调优实战', link: '/spark/notes/08-性能调优实战' },
            { text: '09 Structured Streaming', link: '/spark/notes/09-StructuredStreaming' },
            { text: '10 生态对比与 FAQ', link: '/spark/notes/10-生态对比与FAQ' },
          ],
        },
      ],
      '/flink/': [
        {
          text: 'Flink',
          items: [
            { text: '主题入口', link: '/flink/' },
            { text: '01 概述与定位', link: '/flink/notes/01-概述与定位' },
            { text: '02 架构与运行原理', link: '/flink/notes/02-架构与运行原理' },
            { text: '03 DataStream API 与核心算子', link: '/flink/notes/03-DataStream%20API与核心算子' },
            { text: '04 时间语义与 Watermark', link: '/flink/notes/04-时间语义与Watermark' },
            { text: '05 Window 窗口机制', link: '/flink/notes/05-Window窗口机制' },
            { text: '06 State 与 Checkpoint', link: '/flink/notes/06-State与Checkpoint' },
            { text: '07 Flink SQL 与 Table API', link: '/flink/notes/07-Flink%20SQL与Table%20API' },
            { text: '08 部署与集群规划', link: '/flink/notes/08-部署与集群规划' },
            { text: '09 性能调优与故障排查', link: '/flink/notes/09-性能调优与故障排查' },
            { text: '10 生态对比与 FAQ', link: '/flink/notes/10-生态对比与FAQ' },
          ],
        },
      ],
      '/kafka/': [
        {
          text: 'Kafka',
          items: [
            { text: '主题入口', link: '/kafka/' },
            { text: '01 概述与定位', link: '/kafka/notes/01-概述与定位' },
            { text: '02 架构与核心概念', link: '/kafka/notes/02-架构与核心概念' },
            { text: '03 Producer 生产者原理', link: '/kafka/notes/03-Producer生产者原理' },
            { text: '04 Consumer 消费者原理', link: '/kafka/notes/04-Consumer消费者原理' },
            { text: '05 存储与分区原理', link: '/kafka/notes/05-存储与分区原理' },
            { text: '06 高级特性', link: '/kafka/notes/06-高级特性' },
            { text: '07 部署与集群规划', link: '/kafka/notes/07-部署与集群规划' },
            { text: '08 运维监控与故障排查', link: '/kafka/notes/08-运维监控与故障排查' },
            { text: '09 Kafka 与周边生态', link: '/kafka/notes/09-Kafka与周边生态' },
            { text: '10 生态对比与 FAQ', link: '/kafka/notes/10-生态对比与FAQ' },
          ],
        },
      ],
      '/iceberg/': [
        {
          text: '湖仓一体',
          items: [
            { text: '主题入口', link: '/iceberg/' },
            { text: '01 概述与湖仓一体', link: '/iceberg/notes/01-概述与湖仓一体' },
            { text: '02 架构与元数据层级', link: '/iceberg/notes/02-架构与元数据层级' },
            { text: '03 表格式与文件组织', link: '/iceberg/notes/03-表格式与文件组织' },
            { text: '04 ACID 与快照隔离', link: '/iceberg/notes/04-ACID与快照隔离' },
            { text: '05 分区演进与隐藏分区', link: '/iceberg/notes/05-分区演进与隐藏分区' },
            { text: '06 Time Travel 与版本管理', link: '/iceberg/notes/06-TimeTravel与版本管理' },
            { text: '07 Schema 演进与数据类型', link: '/iceberg/notes/07-Schema演进与数据类型' },
            { text: '08 与 Spark/Flink/Hive 集成', link: '/iceberg/notes/08-与SparkFlinkHive集成' },
            { text: '09 性能优化与实践', link: '/iceberg/notes/09-性能优化与实践' },
            { text: '10 生态对比与 FAQ', link: '/iceberg/notes/10-生态对比与FAQ' },
          ],
        },
      ],
      '/hbase/': [
        {
          text: 'HBase',
          items: [
            { text: '主题入口', link: '/hbase/' },
            { text: '01 概述与定位', link: '/hbase/notes/01-概述与定位' },
            { text: '02 架构与组件', link: '/hbase/notes/02-架构与组件' },
            { text: '03 数据模型与 RowKey 设计', link: '/hbase/notes/03-数据模型与RowKey设计' },
            { text: '04 LSM-Tree 与存储原理', link: '/hbase/notes/04-LSM-Tree与存储原理' },
            { text: '05 API 与 CRUD 实战', link: '/hbase/notes/05-API与CRUD实战' },
            { text: '06 Region 管理与性能调优', link: '/hbase/notes/06-Region管理与性能调优' },
            { text: '07 部署与集群规划', link: '/hbase/notes/07-部署与集群规划' },
            { text: '08 运维监控与故障排查', link: '/hbase/notes/08-运维监控与故障排查' },
            { text: '09 HBase 与周边组件', link: '/hbase/notes/09-HBase与周边组件' },
            { text: '10 生态对比与 FAQ', link: '/hbase/notes/10-生态对比与FAQ' },
          ],
        },
      ],
      '/clickhouse/': [
        {
          text: 'ClickHouse',
          items: [
            { text: '主题入口', link: '/clickhouse/' },
            { text: '01 概述与定位', link: '/clickhouse/notes/01-概述与定位' },
            { text: '02 架构与核心组件', link: '/clickhouse/notes/02-架构与核心组件' },
            { text: '03 MergeTree 引擎家族', link: '/clickhouse/notes/03-MergeTree引擎家族' },
            { text: '04 数据类型与 SQL', link: '/clickhouse/notes/04-数据类型与SQL' },
            { text: '05 分区排序与索引', link: '/clickhouse/notes/05-分区排序与索引' },
            { text: '06 向量化执行与查询原理', link: '/clickhouse/notes/06-向量化执行与查询原理' },
            { text: '07 分布式与集群', link: '/clickhouse/notes/07-分布式与集群' },
            { text: '08 物化视图与 CDC', link: '/clickhouse/notes/08-物化视图与CDC' },
            { text: '09 性能调优与实践', link: '/clickhouse/notes/09-性能调优与实践' },
            { text: '10 生态对比与 FAQ', link: '/clickhouse/notes/10-生态对比与FAQ' },
          ],
        },
      ],
      '/dolphin-scheduler/': [
        {
          text: '海豚调度',
          items: [
            { text: '主题入口', link: '/dolphin-scheduler/' },
            { text: '01 概述与定位', link: '/dolphin-scheduler/notes/01-概述与定位' },
            { text: '02 架构与组件', link: '/dolphin-scheduler/notes/02-架构与组件' },
            { text: '03 核心概念', link: '/dolphin-scheduler/notes/03-核心概念' },
            { text: '04 DAG 与调度', link: '/dolphin-scheduler/notes/04-DAG与调度' },
            { text: '05 任务类型详解', link: '/dolphin-scheduler/notes/05-任务类型详解' },
            { text: '06 参数与时间变量', link: '/dolphin-scheduler/notes/06-参数传递与时间变量' },
            { text: '07 资源数据源与环境', link: '/dolphin-scheduler/notes/07-资源数据源与环境' },
            { text: '08 部署与快速上手', link: '/dolphin-scheduler/notes/08-部署与快速上手' },
            { text: '09 运维与故障排查', link: '/dolphin-scheduler/notes/09-运维实践与故障排查' },
            { text: '10 生态对比与 FAQ', link: '/dolphin-scheduler/notes/10-生态对比与FAQ' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/milsevol/yili-ai-xuexi' },
    ],

    search: {
      provider: 'local',
    },

    outline: {
      label: '本页目录',
    },

    docFooter: {
      prev: '上一页',
      next: '下一页',
    },

    lastUpdated: {
      text: '最后更新',
    },

    returnToTopLabel: '回到顶部',
    sidebarMenuLabel: '菜单',
    darkModeSwitchLabel: '主题',
  },
})
