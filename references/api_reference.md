# SMT 系统 API 接口参考

## 通用信息

- **Base URL**: `https://smarttalk-asia-test.yamimeal.ca`
- **API Key**: `Hvcav176asb`
- **请求头**: `Content-Type: application/json`, `X-API-KEY: <api-key>`

---

## 1. 创建会话

创建新的对话会话，返回 sessionId 供后续使用。

- **方法**: `POST`
- **路径**: `/api/RealtimeHttpGateway/sessions`

### 请求体

```json
{
  "assistantId": 357,
  "region": "US"
}
```

### 响应示例

```json
{
  "sessionId": "de3d40b2cb1f48908c6da1bde0062e69",
  "providerSessionId": "",
  "assistantId": 357,
  "region": 0,
  "status": "idle_waiting",
  "createdAt": "2026-07-17T08:10:21.0194176+00:00"
}
```

### 说明

- `sessionId` 是后续发送消息和结束会话的必需参数
- `status` 为 `idle_waiting` 表示会话已就绪

---

## 2. 发送消息

向指定会话发送文本消息，AI 会回复。

- **方法**: `POST`
- **路径**: `/api/RealtimeHttpGateway/sessions/{sessionId}/messages`

### 请求体

```json
{
  "text": "你好，我要下单",
  "timeoutMs": 30000
}
```

### 响应示例

```json
{
  "sessionId": "de3d40b2cb1f48908c6da1bde0062e69",
  "providerSessionId": "329cf240-fe94-40cf-a51a-383846d980ec",
  "inputText": "可以下单了吗",
  "outputText": "好的，已经在为您处理订单。",
  "completed": true,
  "turnNumber": 10,
  "inputAudioDurationMs": 1950,
  "tailSilenceMs": 0,
  "waitTimeoutMs": 30000,
  "completionReason": "ai_turn_completed",
  "lastEventType": "AiTurnCompleted",
  "lastError": "",
  "createdAt": "2026-07-17T08:14:42.6753729+00:00"
}
```

### 说明

- `outputText` 是 AI 的回复文本
- `completionReason` 为 `ai_turn_completed` 表示 AI 正常回复完成
- `turnNumber` 表示当前是第几轮对话

---

## 3. 结束会话

结束指定的对话会话。

- **方法**: `DELETE`
- **路径**: `/api/RealtimeHttpGateway/sessions/{sessionId}?reason=http_client_disconnect`

### 响应示例

```json
{
  "sessionId": "de3d40b2cb1f48908c6da1bde0062e69",
  "providerSessionId": "329cf240-fe94-40cf-a51a-383846d980ec",
  "closed": true,
  "reason": "http_client_disconnect"
}
```

### 说明

- `closed` 为 `true` 表示会话已成功关闭
- `reason` 参数可自定义关闭原因
