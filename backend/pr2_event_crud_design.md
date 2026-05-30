# PR2 设计说明：日程 CRUD API

## 1. PR2 目标

PR2 负责完成注册登录与非 AI 的日程管理能力，为后续语音指令执行提供稳定工具层。

本 PR 需要交付：

- 用户注册 API；
- 用户登录 API；
- Bearer Token 认证；
- SQLite 事件表；
- 事件创建 API；
- 事件查询 API；
- 事件详情 API；
- 事件修改 API；
- 事件删除 API；
- 简单循环事件支持；
- 基础错误处理。

## 2. 非目标

PR2 不处理以下内容：

- 自然语言解析；
- 语音输入；
- 前端页面；
- 多用户权限；
- 循环事件例外日期；
- 单次循环实例的独立修改或删除。

## 3. 认证设计

### 3.1 支持范围

PR2 实现最小可用注册登录：

- 用户通过 `username` 和 `password` 注册；
- 登录成功后返回 `access_token`；
- 事件 API 需要通过 `Authorization: Bearer <token>` 访问；
- 每个用户只能访问自己的事件。

密码使用 Werkzeug password hash 存储。虽然 Hackathon 不做复杂安全能力，但这个实现成本很低，可以避免明文密码。

### 3.2 认证 API

#### 注册

`POST /api/auth/register`

请求：

```json
{
  "username": "demo",
  "password": "password123"
}
```

响应：

```json
{
  "user": {
    "id": 1,
    "username": "demo"
  },
  "access_token": "<token>"
}
```

#### 登录

`POST /api/auth/login`

请求：

```json
{
  "username": "demo",
  "password": "password123"
}
```

响应：

```json
{
  "user": {
    "id": 1,
    "username": "demo"
  },
  "access_token": "<token>"
}
```

## 4. 数据模型

### 4.1 用户表

用户表 `users` 字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | integer | 自增主键 |
| `username` | text | 用户名，唯一 |
| `password_hash` | text | 密码哈希 |
| `created_at` | text | 创建时间 |
| `updated_at` | text | 更新时间 |

### 4.2 事件表

事件表 `events` 字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | integer | 自增主键 |
| `user_id` | integer | 事件所属用户 |
| `title` | text | 日程标题，必填 |
| `start_time` | text | ISO datetime，首次开始时间 |
| `end_time` | text | ISO datetime，首次结束时间 |
| `notes` | text | 备注，可为空 |
| `recurrence_type` | text | `none`、`daily`、`weekly`、`monthly` |
| `recurrence_interval` | integer | 循环间隔，默认 `1` |
| `recurrence_until` | text | 循环结束时间，可为空 |
| `created_at` | text | 创建时间 |
| `updated_at` | text | 更新时间 |

## 5. 循环事件设计

### 5.1 支持范围

PR2 只支持简单循环：

- `none`：不循环；
- `daily`：每 N 天；
- `weekly`：每 N 周；
- `monthly`：每 N 月。

示例：

```json
{
  "title": "站会",
  "start_time": "2026-06-01T10:00:00+08:00",
  "end_time": "2026-06-01T10:30:00+08:00",
  "recurrence_type": "daily",
  "recurrence_interval": 1,
  "recurrence_until": "2026-06-05T23:59:59+08:00"
}
```

### 5.2 查询行为

查询接口返回指定时间范围内的事件实例。

- 非循环事件：如果与查询范围重叠，则返回一次；
- 循环事件：根据 `recurrence_type` 展开为多个实例；
- 返回结果包含 `series_id`，指向原始事件 ID；
- 返回结果包含 `is_recurring`，标识是否来自循环事件。

### 5.3 修改和删除行为

PR2 中，修改和删除都作用于整个事件系列。

暂不支持：

- 只修改某一次循环实例；
- 只删除某一次循环实例；
- 例外日期；
- 跳过节假日。

这个限制可以降低复杂度，也更适合两天 Hackathon 的节奏。

## 6. 事件 API 设计

所有事件 API 都需要认证：

```text
Authorization: Bearer <token>
```

### 6.1 查询事件

`GET /api/events`

支持参数：

- `date`：查询某一天，例如 `2026-06-01`；
- `start`：查询范围开始 ISO datetime；
- `end`：查询范围结束 ISO datetime。

响应：

```json
{
  "events": [
    {
      "id": 1,
      "user_id": 1,
      "series_id": 1,
      "title": "站会",
      "start_time": "2026-06-01T10:00:00+08:00",
      "end_time": "2026-06-01T10:30:00+08:00",
      "notes": null,
      "recurrence_type": "daily",
      "recurrence_interval": 1,
      "recurrence_until": "2026-06-05T23:59:59+08:00",
      "is_recurring": true
    }
  ]
}
```

### 6.2 创建事件

`POST /api/events`

必填字段：

- `title`；
- `start_time`。

可选字段：

- `end_time`，默认开始后 1 小时；
- `notes`；
- `recurrence_type`，默认 `none`；
- `recurrence_interval`，默认 `1`；
- `recurrence_until`。

### 6.3 查询详情

`GET /api/events/{id}`

返回原始事件，不展开循环实例。

### 6.4 修改事件

`PATCH /api/events/{id}`

允许修改：

- `title`；
- `start_time`；
- `end_time`；
- `notes`；
- `recurrence_type`；
- `recurrence_interval`；
- `recurrence_until`。

### 6.5 删除事件

`DELETE /api/events/{id}`

删除原始事件。若是循环事件，则删除整个系列。

## 7. 错误处理

统一错误响应：

```json
{
  "error": "event not found"
}
```

常见状态码：

- `400`：请求参数非法；
- `401`：未登录或 token 无效；
- `404`：事件不存在；
- `201`：创建成功；
- `204`：删除成功。

## 8. PR2 Commit 规划

所有 commit message 使用 Angular 风格：

1. `feat - add auth database schema`
2. `feat - add register and login api`
3. `feat - add recurring event crud api`
4. `docs - add pr2 api design`
5. `fix - improve event validation`
