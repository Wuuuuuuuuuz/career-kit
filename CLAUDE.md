# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供核心指导原则。请在编写、修改或审查代码前，务必仔细阅读并严格遵守本文件的所有规范。

## 编码规范
编码前思考 (Think Before Coding)：避免不确认需求就动手。
简洁优先 (Simplicity First)：用最少的代码解决问题，避免过度工程。
精准修改 (Surgical Changes)：只修改必要的部分，不碰无关代码。
目标驱动执行 (Goal-Driven Execution)：确保改动有明确的验收标准。
修复BUG时应该先定位BUG，在分析代码困难时应当编写测试脚本。
设计方案前尽量先与用户沟通，确保理解需求，避免设计错误。
善于借鉴github现有项目的优秀思路。

本项目是多人协作开发
每次改动确认成功后(未成功时不需要)都要git push，push时要明确改动内容