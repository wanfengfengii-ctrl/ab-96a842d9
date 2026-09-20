# 海底光缆色散补偿盒排布工作台

更换放大站后重排色散补偿盒（DCM）的全栈工作台。工程师在浏览器中导入或编辑
**2–80 段**线路与段后站点数据，调用真实 API，在**全局合法方案**中按字典序
依次最小化：

1. **安装盒数**最少；
2. **总插损**最小；
3. **末站累计值的绝对残差**最小。

- 唯一最优：返回完整选盒序列；
- 存在并列：返回按“各站编号序列”（不装排在最前）字典序排序的**前两份见证**；
- 无合法方案：返回**首个可达状态集合变空的站点**编号；
- 输入错误：返回 422 并按 `站点 → 字段` 精确定位。

## 精确性

增量、区间、修正量、插损均为**最多三位小数**。服务端用 `Decimal` 解析 JSON
字面量（不经过 `float`），统一 ×1000 缩放为整数；求解器全程只做整数运算，
缩放后数值必须落在 `[-20000, 20000]`，插损非负。前端以字符串编辑数值，
并提供精确的毫单位格式化。

## 算法（禁止枚举全部组合）

按“**站点 × 可达累计整数值**”做分层动态规划：

- 每个可达值保留按 `(安装数, 总插损)` 的非支配前沿（同值下安装数更多且
  插损不更小的状态被剪枝）；
- 每个前沿状态只保留按各站编号序列字典序最小的两条见证路径，节点按
  `(前驱名次, 本站决策)` 物理排序，使 id 即字典序名次，支持 O(1) 比较与回溯；
- 末站跨所有可达值比较三级目标取全局最优，并输出前两份见证。

满规模 80 站 × 12 盒的求解时间为毫秒级（验收中以 10 秒为上限），
与 13⁸⁰ 的暴力枚举无关。正确性已用 5500+ 组随机小规模对拍（对照完整枚举）验证。

## 目录

```
api/      Python 3.13 + FastAPI（精确校验 + 整数 DP 求解器）
web/      React + TypeScript（Vite 构建，nginx 托管并反代 /api）
verify/   Compose “verify” 可执行验收服务（标准库，端到端 HTTP 验收）
docker-compose.yml
```

## 运行（Docker Compose）

```bash
cp .env.example .env          # 可选：修改宿主机端口
docker compose up --build
```

- Web：http://localhost:8080  （`WEB_HOST_PORT` 可配置）
- API：http://localhost:8000  （`API_HOST_PORT` 可配置；含 `/docs`）
- 健康检查：`GET /health`（Web 与 API 均提供，镜像内 HEALTHCHECK 与
  Compose healthcheck 双重配置）

## 验收

```bash
docker compose build verify
docker compose run --rm verify
```

`verify` 会等待 Web/API 健康，然后通过真实 HTTP 请求核验：双端健康检查、
三级目标优先级、并列前二见证（含跨站排序）、不可行站点定位、字段级输入
定位、三位小数精确性、80×12 性能与非枚举、以及经 Web 反代的求解调用。

## 本地开发

```bash
# API
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r api/requirements.txt
uvicorn --app-dir api app.main:app --reload --port 8000

# Web
cd web && npm install && npm run dev
```

## 请求 / 响应示例

请求（数值用数字或字符串均可，服务端按 Decimal 精确解析）：

```json
{
  "segments": [{ "increment": "3.200" }, { "increment": "-1.500" }],
  "stations": [
    { "lower": "0", "upper": "6",
      "boxes": [{ "id": "A1", "correction": "0.500", "loss": "1.200" }] },
    { "lower": "0", "upper": "5", "boxes": [] }
  ]
}
```

最优响应（数值均为 ×1000 的整数）：

```json
{
  "status": "optimal",
  "objective": { "boxes_installed": 1, "total_loss": 1200,
                 "final_abs_residual": 2200 },
  "unique": true,
  "witnesses": [{ "sequence": [
    { "station": 1, "choice": { "id": "A1", "correction": 500, "loss": 1200 },
      "cumulative": 3700 },
    { "station": 2, "choice": null, "cumulative": 2200 }
  ] }]
}
```

无可行方案：`{ "status": "infeasible", "infeasible_station": 3, ... }`
输入错误：HTTP 422，`errors[].field` 形如 `stations[2].boxes[0].loss`。
