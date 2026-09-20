# 海底光缆色散补偿盒排布工作台

更换放大站后重排色散补偿盒的全栈工作台。工程师在浏览器中导入或编辑
**2–80 段**线路，调用真实 FastAPI 计算服务，在**全局合法方案**中依次最小化

1. 安装盒数
2. 候选盒总插损
3. 末站累计色散的绝对残差

逐站贪心回零可能让后续站点越界；本服务使用分层多标签动态规划求全局最优，
**不枚举任何组合**。

## 精确整数语义

- 增量、区间上下界、候选盒修正量与插损均为**至多三位小数**，缺省为 0。
- 所有数值乘 1000 缩放为整数，缩放后必须落在 `−20000 … 20000`（插损额外要求非负）。
- 全程整数比较（Python 端 `Decimal → int`，不使用 `float` 参与判定）。
- 站点安全区间为**闭区间**，边界可达。
- 累计初值为 0；每站**不装盒或恰好装一盒**，盒编号为本站内唯一正整数，每站至多 12 个候选盒。
- 目标唯一时返回完整选盒序列；目标并列时，额外返回按“各站编号序列”（不装盒视为 `null`，排在所有编号之前）字典序排序的**前两份见证**。

## 算法（不枚举组合）

`backend/app/solver.py` 实现 k=2 多标签分层 DP：

- 状态为“累计色散整数值”，每层（每站）对每个值仅保留按
  `(安装数, 总插损, 编号序列)` 排序的前 2 个标签；
- 序列比较通过**归纳稠密排名**降为整数比较（每层仅对幸存者排序一次）；
- 末层再按 `(安装数, 总插损, |末值|, 序列排名)` 决出最优与前两份见证；
- 某站处理后可达集合首次为空，即返回该站作为无解定位。

复杂度 `O(N · V · B · log V)`（N ≤ 80，V ≤ 40001，B ≤ 12），最坏规模实测约 1 秒。
正确性由 `backend/tests/test_solver.py` 中 300 组随机实例与**暴力枚举预言机**对照保证
（枚举只存在于测试，生产代码不枚举）。

## 运行（Docker Compose）

```bash
docker compose up --build
```

- Web（React + nginx）：http://localhost:8080
- API（FastAPI）：http://localhost:8000 ，健康检查 `GET /healthz`
- Web 容器自带 `/healthz` 健康检查，并反向代理 `/api/*` 到 API。

宿主机端口可配置（环境变量或 `.env`）：

```bash
WEB_PORT=18080 API_PORT=18000 docker compose up --build
cp .env.example .env   # 持久化配置
```

### 验收服务 verify

```bash
docker compose run --rm verify
```

`verify` 服务在 compose 网络内对**真实运行中的 API**发起 HTTP 验收
（健康检查、唯一最优、并列双见证、贪心反例、无解锁站、422 字段定位、
千分位精确性、80×12 规模性能等），全部通过返回码为 0。

## API

`POST /api/solve`

```json
{
  "stations": [
    {
      "increment": 6,
      "lower": 0,
      "upper": 8,
      "boxes": [
        { "id": 1, "correction": -3, "loss": 0.5 }
      ]
    }
  ]
}
```

响应：

- `200` `{"status":"optimal", "stations":[...], "witnesses":[[...]], "summary":{...}}`
- `409` `{"status":"infeasible", "failed_station": <首个可达集为空的站，1 基>, ...}`
- `422` `{"status":"invalid", "errors":[{"station":2,"field":"boxes[0].loss","message":"..."}]}`

另有 `GET /healthz` 与 `GET /api/limits`。

## 本地开发（无 Docker）

```bash
# 后端（要求 Python 3.13；3.11+ 亦可本地开发运行）
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
python tests/test_solver.py           # 单元 + 随机对照测试
python acceptance/verify.py http://127.0.0.1:8000

# 前端
cd frontend
npm install
npm run dev        # http://localhost:5173 ，自动代理 /api 到 :8000
```

## 目录

```
backend/
  app/solver.py        # 精确整数 k=2 多标签 DP
  app/validation.py    # 定点解析与定位校验
  app/main.py          # FastAPI 路由
  tests/               # 含暴力枚举预言机的对照测试
  acceptance/verify.py # compose verify 验收脚本
frontend/
  src/                 # React + TypeScript 工作台
docker-compose.yml     # api / web（含健康检查）/ verify
examples/              # 导入示例（含并列示例 tie-line.json）
```
