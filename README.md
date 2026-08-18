# 番茄小说 CLI 伪装阅读器

在终端里"边开发边读小说"——阅读界面伪装成 Vim / IDE / 日志终端,
同时通过番茄官方网页 API 与手机 App 双向同步阅读进度。

> 仅供个人学习与技术研究。内容版权归番茄小说及原作者所有。
> 本项目不提供、不存储任何小说内容,正文通过你自己的登录态获取。

## 完整章节正文(可选但推荐)

番茄网页对靠后章节只提供约 150 字试读。要读完整正文,
需本地跑一个 unidbg 签名服务(fqnovel-unidbg),它模拟 App 的
`libmetasec_ml.so` 签名库,以 App 身份请求官方内容 API。

### Docker 方式(推荐)

```bash
# 1. 构建镜像(需先本地编译出 JAR)
git clone https://github.com/mtongle/fqnovel-unidbg.git && cd fqnovel-unidbg
git lfs install && git lfs pull          # 拉取 SO 库
mvn clean package -DskipTests            # 编译(Java 17+ / Maven)
docker build -t fqnovel-unidbg:local .   # 打镜像

# 2. 启动(开机自启,失败自动重启)
./docker-run.sh start
```

### Java 直接运行

```bash
java -jar target/unidbg-boot-server-*.jar
```

服务监听 `http://127.0.0.1:8099`。阅读器会自动探测:
- 服务可用 → 读完整章节
- 服务不可用 → 回退网页试读(靠前章节仍是全文)

## 配置

在项目根目录放置 `.env`(参考 `.env.example`):

```bash
FANQIE_COOKIE="粘贴番茄小说网页 Cookie"
UNIDBG_BASE="http://127.0.0.1:8099"   # unidbg 服务地址
FANQIE_DISGUISE="vim"                 # vim / ide / logtail
```

## 快捷键

| 键 | 功能 |
|---|---|
| `n` / `p` | 下一章 / 上一章 |
| `d` | 切换伪装模式(流式输出) |
| `space` | 流式模式暂停 / 继续 |
| `c` | 章节目录 |
| `q` | 返回书架 |
| `Ctrl+S` | 打开设置 |
| `Ctrl+Q` | 退出 |

## 进度同步

打开书时从云端拉取进度自动续读;每读完一章上报云端,
手机 App 打开同一本书会跳到对应章节(章节级,不含章内页数)。