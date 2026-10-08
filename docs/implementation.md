# 五阶段实施计划

日期：2026-10-09。目标与验收以 [设计文档](design.md) 为准。用户已要求设计后直接执行，不再请求重复设计审批。记录当前推进与证据，不以未执行的CI或他平台流程冒充验证。

## 代码边界

- 现有仓库：`univpn_forward/`保留零依赖TCP兼容入口。
- `univpn_client/`：新增配置、凭据、控制器、平台授权、CLI、desktop bridge与本地UI。
- `scripts/`：核心补丁准备、平台构建、发行和隐私检查。
- `native/`：上游基线说明、可应用补丁系列、许可证与源码获取/构建说明；不混入私有配置。
- OpenConnect工作目录：独立 `docs/huawei-univpn-protocol` 分支上的原文档补丁，另开 `feature/univpn-native` 实现原生；最终导出可审核的系列补丁。
- `tests/`：协议、模拟网关、控制器、配置凭据、UI与包装验证。
- `.local/`：真实地址、读取私有凭据的探测脚本、原始报告和构建日志，始终忽略。

## 阶段1：能力与可靠性

- [ ] 创建独立探测脚本，使用已有私有凭据来源；认证数据不打印。记录认证/VIP TLV的结构元数据，只在私有报告保留原值。
- [ ] 验证允许目标清单中的多个目标/端口，不扫描网段。
- [ ] 创建确定性UDP/ICMP探测、长空闲、大文件哈希、并发连接；为断网/关闭通道提供有界测试。记录外层TLS与内层UDP的区别。
- [ ] 发布脱敏的能力矩阵和失败边界；保留原自动连接服务及现有训练。

检查命令：`python3 -m unittest discover -s tests -v`；真实探测脚本仅从`.local/`运行。每个测试有总时限、清理动作和恢复检查。

## 阶段2：OpenConnect原生

- [ ] 准备上游构建依赖并先编译未修改基线，保留构建日志。
- [ ] 新建`univpn.c`和协议私有状态；注册protocol、函数声明、Makefile源列表及析构清理。
- [ ] 先实现带长度校验的framing/TLV/IPv4解析；添加可独立运行的C测试，覆盖分片/错误/未知字段。
- [ ] 实现认证表单、FirstConnect、AUTH、REQVIP、两个独立TLS通道；保持对端身份校验。用本地模拟TLS网关验证认证、取消、超时和错误，不使用实际密码。
- [ ] 实现事件循环帧读取/写缓冲、TUN包队列、保活、错误/重连/析构；测试partial write和错误帧不会污染下一帧。
- [ ] 执行C测试、模拟网关集成、sanitizers和上游适用检查；在新私有测试连接验证真实数据收发。
- [ ] 权限允许时配置临时utun及单个测试目标路由，验证普通SSH/UDP/ICMP以及断开撤销；没有权限不标通过。

验收：新二进制`openconnect --protocol=univpn --help`列出协议；模拟和真实测试清楚区分；TLS校验默认开启；本机实际运行证据包含版本、平台、测试内容和结果。

## 阶段3：管理和CLI

接口文件与职责：

- `profiles.py`：`ProfileStore(path)`负责验证、稳定ID、原子保存、导入导出和上次选择。
- `credentials.py`：`CredentialStore`仅使用系统安全库；`get(account_id)`不直接暴露给网页。
- `engine.py`：`ConnectionController`拥有一个连接；`connect(profile_id, account_id)`、`disconnect()`、`snapshot()`、`logs()`线程安全、有界重连、实例锁。
- `platforms.py`：启动/授权/停止当前网络进程，凭据走管道；PID与会话来源校验。
- `cli.py`：`univpn-client profiles/accounts/connect/disconnect/status/logs/desktop`共用管理层，命令输出没有密码。

- [ ] 先添加配置/凭据/控制状态测试，再实现；重点验证两个账户并存、导出不含密码、坏参数、不可用安全库和原子写。
- [ ] 实现CLI参数和管理命令，mock核心失败/成功/退出、PID复用、重复连接、取消、超时和退避；认证错误不无限重连。
- [ ] 本机用测试凭据Keychain项验证保存、读取、删除；不改动原私人项。验证CLI和桌面读相同配置。

## 阶段4：桌面与安装

- [ ] 本地UI文件`ui/index.html`、`app.js`、`styles.css`：完成侧栏/连接/配置/账户/日志/设置及浅暗色；不加载远端资产。
- [ ] `desktop.py`提供有限bridge方法；所有输入走同一验证；密码只允许写入/本次连接，不提供读取API。
- [ ] 实现异步进度、取消、切换确认、日志上限、关闭/退出语义；实际操作所有不会改动现有网络的界面功能。
- [ ] `scripts/build_desktop.py`按宿主架构冻结CLI和desktop；缺失原生核心或第三方许可时失败。平台安装布局分别实现DMG、Windows安装/便携、deb/便携。
- [ ] 添加Mac arm64/Intel、Windows、Linux构建workflow；不能建仓触发CI，因此本机无法运行的构建明确“未执行”，交叉编译结果单独记录。
- [ ] Mac app实际启动并检查UI与CLI版本、凭据和配置；网络功能只连接新的测试实例。

## 阶段5：回归和提交前准备

- [ ] 执行适用测试和完整本机检查；公开`docs/validation.md`标出真实运行、模拟、构建、未验证。
- [ ] 单一版本、完整README quickstart、许可、第三方通知、源码/补丁、changelog、发行说明和SHA256清单。
- [ ] 逐文件及Git历史检查私有主机、账户、密码、会话数据和机器路径；发行包重复扫描。
- [ ] 上游新增功能文档和测试，并导出分阶段功能补丁、MR说明、基线、应用/编译/测试步骤，保留DCO待本人认证。
- [ ] 独立项目本地commit准备好，不创建GitHub远端，不注册GitLab，不fork、不push、不发issue/comment/email/MR。

## 当前证据

2026-10-09：TCP原型alpha已通过13项测试、真实SSH/256KiB双向传输/65秒空闲/并发和错pin拒绝；不代表原生VPN、系统路由或其他桌面平台已完成。已下载当前OpenConnect基线并准备文档补丁，原生阶段尚未执行。
