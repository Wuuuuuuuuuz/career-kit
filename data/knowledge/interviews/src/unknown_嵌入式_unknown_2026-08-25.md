---
source: nowcoder
url: https://www.nowcoder.com/feed/main/detail/cc752829970a498eaa71bbc196b8fad2
company: 
position: 嵌入式
round: 
date: 2026-08-25
tags: []
---

##  - 嵌入式

**日期**：2026-08-25

## 面试内容

把 0x11223344 写入一个变量，再用 unsigned char 指针读取首字节。如果首字节是 0x44，说明当前平台是哪种字节序？如何用 union 写一段判断代码？...主循环和中断会并发更新一个多字节变量。volatile 只解决编译器优化问题，无法解决什么？请举出一个需要临界区或原子操作的场景，并说明单字节标志位为何可能例外。...如果某个 int 成员的地址没有 4 字节对齐，对 32 位总线访问会产生什么影响？...有一个结构体成员顺序为 char、int、short，在 32 位平台上按 4 字节对齐编译，实际 sizeof 是多少？如果把 short 放到 int 前面，大小是否会变化？请说明补位规则。