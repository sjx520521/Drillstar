DrillStar 文档依赖离线包目录

来源:
- 《DrillStar钻井数据采集分析平台V1.0》3.4 开发环境 / 表3.1 主要使用包及版本表

当前目录说明:
- requirements_doc.txt: 文档中列出的包和版本
- requirements_bundle_verified.txt: 已实际离线安装验证通过的完整冻结依赖清单
- install_offline.ps1: 使用当前目录中的离线包执行安装

离线安装示例:
PowerShell:
  .\plugins_offline\install_offline.ps1

说明:
- `nidaqmx` 是 Python 接口包，若要实际连接 NI 采集卡，目标电脑通常还需要额外安装 NI 官方驱动/运行环境。
- MySQL 功能还需要目标电脑可访问 MySQL 服务，本目录不包含数据库服务本体。
- 安装脚本会优先使用 `requirements_bundle_verified.txt`，以保证安装结果与已验证环境一致。
