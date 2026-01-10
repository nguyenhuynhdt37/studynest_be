# Chat SQL API - Hướng dẫn Frontend

## Tổng quan

API cho phép người dùng hỏi đáp về dữ liệu bằng ngôn ngữ tự nhiên. Hệ thống tự động:

1. Phân loại câu hỏi (chào hỏi / hỏi tiếp / hỏi mới)
2. Sinh SQL từ câu hỏi
3. Thực thi và trả về kết quả bằng ngôn ngữ tự nhiên

---

## Endpoint

```
POST /api/v1/chat-sql/complete
```

**Authentication:** Bearer Token (bắt buộc đăng nhập)

---

## Request

```typescript
interface ChatRequest {
  question: string; // Câu hỏi của người dùng (1-500 ký tự)
  history?: string[]; // Lịch sử chat trước đó (tối đa 10 tin)
}
```

### Ví dụ Request

```json
{
  "question": "Có bao nhiêu khóa học của tôi?",
  "history": []
}
```

```json
{
  "question": "Giải thích thêm đi",
  "history": [
    "Có bao nhiêu khóa học của tôi?",
    "Bạn hiện có 5 khóa học đang hoạt động trên hệ thống."
  ]
}
```

---

## Response

```typescript
interface ChatResponse {
  response: string; // Câu trả lời bằng ngôn ngữ tự nhiên
}
```

### Ví dụ Response

**Câu hỏi về dữ liệu:**

```json
{
  "response": "Bạn hiện có 5 khóa học đang hoạt động trên hệ thống, với tổng cộng 127 học viên đã đăng ký."
}
```

**Câu chào hỏi:**

```json
{
  "response": "Xin chào! Tôi là trợ lý SQL. Bạn có thể hỏi tôi về dữ liệu khóa học, học viên, doanh thu... Ví dụ: 'Có bao nhiêu khóa học đang active?'"
}
```

**Câu hỏi không hợp lệ:**

```json
{
  "response": "Xin lỗi, tôi chưa hiểu câu hỏi của bạn. Bạn có thể hỏi về: khóa học của tôi, tiến độ học, doanh thu, hoặc số học viên."
}
```

---

## Ví dụ Fetch API

```typescript
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

async function sendChatMessage(
  question: string,
  chatHistory: ChatMessage[],
  token: string
): Promise<string> {
  // Lấy history từ chat messages (chỉ lấy content)
  const history = chatHistory.map((msg) => msg.content).slice(-10);

  const response = await fetch("/api/v1/chat-sql/complete", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      question,
      history,
    }),
  });

  if (!response.ok) {
    throw new Error("API Error");
  }

  const data = await response.json();
  return data.response;
}
```

---

## Ví dụ React Component

```tsx
import { useState } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function ChatSQL() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      // Lấy history (tối đa 10 tin nhắn gần nhất)
      const history = messages.map((m) => m.content).slice(-10);

      const res = await fetch("/api/v1/chat-sql/complete", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: JSON.stringify({
          question: input,
          history,
        }),
      });

      const data = await res.json();

      const assistantMessage: Message = {
        role: "assistant",
        content: data.response,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        role: "assistant",
        content: "Đã xảy ra lỗi. Vui lòng thử lại.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {loading && <div className="message assistant">Đang xử lý...</div>}
      </div>

      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Hỏi về dữ liệu của bạn..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading}>
          Gửi
        </button>
      </div>
    </div>
  );
}
```

---

## Các câu hỏi mẫu

### Cho Student:

- "Tôi đã đăng ký bao nhiêu khóa học?"
- "Tiến độ học của tôi như thế nào?"
- "Khóa học nào tôi chưa hoàn thành?"

### Cho Instructor:

- "Doanh thu tháng này của tôi là bao nhiêu?"
- "Top 5 khóa học có nhiều học viên nhất"
- "Có bao nhiêu học viên mới trong tuần này?"
- "Rating trung bình các khóa học của tôi"

### Cho Admin:

- "Tổng doanh thu hệ thống tháng này"
- "Top 10 giảng viên có doanh thu cao nhất"
- "Số lượng người dùng mới trong 30 ngày"

---

## Lưu ý Quan Trọng

1. **Context Awareness (Ngữ cảnh)**:

   - Hệ thống hỗ trợ hỏi nối tiếp. Ví dụ:
     - Q1: "Tìm khóa học Python" -> AI trả danh sách.
     - Q2: "Cái rẻ nhất giá bao nhiêu?" -> AI cần biết Q1 để hiểu "cái rẻ nhất" là trong danh sách Python.
   - **Frontend PHẢI gửi `history`** để tính năng này hoạt động. Nếu `history` rỗng, AI sẽ xử lý Q2 như một câu hỏi độc lập (và có thể không hiểu).
   - Nên gửi tối đa **5-10 tin nhắn gần nhất** để đảm bảo performance.

2. **Authorization**: API tự động filter dữ liệu theo role:

   - **Student**: Chỉ xem dữ liệu cá nhân + khóa học công khai.
   - **Instructor**: Xem khóa học và thu nhập của mình.
   - **Admin**: Xem toàn bộ hệ thống.

3. **Rate Limit**: Khuyến nghị không gọi quá 10 request/phút.

---

## Error Handling

API luôn trả về response thân thiện, không có technical error. Nếu HTTP status không phải 200:

| Status | Ý nghĩa                                      |
| ------ | -------------------------------------------- |
| 401    | Chưa đăng nhập                               |
| 422    | Request không hợp lệ (question quá ngắn/dài) |
| 500    | Lỗi server                                   |

```typescript
if (!response.ok) {
  if (response.status === 401) {
    // Redirect to login
  } else {
    // Show generic error message
  }
}
```
