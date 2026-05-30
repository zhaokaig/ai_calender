import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Keyboard,
  LogOut,
  Mic,
  Plus,
  Save,
  Send,
  Trash2,
  X,
} from "lucide-react";
import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const TOKEN_KEY = "ai_calendar_access_token";
const USER_KEY = "ai_calendar_user";

const recurrenceLabels = {
  none: "不重复",
  daily: "每天",
  weekly: "每周",
  monthly: "每月",
};

function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem(USER_KEY);
    return stored ? JSON.parse(stored) : null;
  });

  const handleAuthenticated = (payload) => {
    localStorage.setItem(TOKEN_KEY, payload.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(payload.user));
    setToken(payload.access_token);
    setUser(payload.user);
  };

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  };

  if (!token) {
    return <AuthPage onAuthenticated={handleAuthenticated} />;
  }

  return <CalendarPage token={token} user={user} onLogout={handleLogout} />;
}

function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const submitLabel = mode === "login" ? "登录" : "注册";

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const payload = await apiRequest(`/api/auth/${mode}`, {
        method: "POST",
        body: { username, password },
      });
      onAuthenticated(payload);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="brand-mark">
          <CalendarDays size={30} aria-hidden="true" />
          <div>
            <p>AI Calendar</p>
            <span>后端测试前端</span>
          </div>
        </div>

        <div className="auth-tabs" role="tablist" aria-label="选择登录或注册">
          <button
            className={mode === "login" ? "active" : ""}
            type="button"
            onClick={() => setMode("login")}
          >
            登录
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            type="button"
            onClick={() => setMode("register")}
          >
            注册
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            用户名
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="demo"
              required
            />
          </label>
          <label>
            密码
            <input
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="至少 6 位"
              required
              minLength={6}
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button className="primary-button" disabled={isLoading} type="submit">
            {isLoading ? "处理中..." : submitLabel}
          </button>
        </form>
      </section>
    </main>
  );
}

function CalendarPage({ token, user, onLogout }) {
  const [currentMonth, setCurrentMonth] = useState(startOfMonth(new Date()));
  const [selectedDate, setSelectedDate] = useState(toDateKey(new Date()));
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [modalState, setModalState] = useState(null);

  const monthRange = useMemo(() => getMonthRange(currentMonth), [currentMonth]);
  const eventsByDate = useMemo(() => groupEventsByDate(events), [events]);
  const selectedEvents = eventsByDate[selectedDate] || [];

  const loadEvents = async () => {
    setIsLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({
        start: monthRange.start.toISOString(),
        end: monthRange.end.toISOString(),
      });
      const payload = await apiRequest(`/api/events?${query}`, { token });
      setEvents(payload.events || []);
    } catch (requestError) {
      if (requestError.status === 401) {
        onLogout();
        return;
      }
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, [monthRange.start.getTime(), monthRange.end.getTime()]);

  const handleSaveEvent = async (formData, eventId) => {
    setError("");
    try {
      if (eventId) {
        await apiRequest(`/api/events/${eventId}`, {
          method: "PATCH",
          token,
          body: formData,
        });
      } else {
        await apiRequest("/api/events", {
          method: "POST",
          token,
          body: formData,
        });
      }
      setModalState(null);
      await loadEvents();
    } catch (requestError) {
      if (requestError.status === 401) {
        onLogout();
        return;
      }
      throw requestError;
    }
  };

  const handleDeleteEvent = async (eventId) => {
    setError("");
    try {
      await apiRequest(`/api/events/${eventId}`, {
        method: "DELETE",
        token,
      });
      setModalState(null);
      await loadEvents();
    } catch (requestError) {
      if (requestError.status === 401) {
        onLogout();
        return;
      }
      throw requestError;
    }
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">AI Calendar</p>
          <h1>{formatMonthTitle(currentMonth)}</h1>
        </div>
        <div className="header-actions">
          <span className="user-pill">{user?.username || "Demo User"}</span>
          <button className="icon-button" type="button" title="退出登录" onClick={onLogout}>
            <LogOut size={18} aria-hidden="true" />
          </button>
          <button
            className="add-button"
            type="button"
            onClick={() => setModalState({ mode: "create", date: selectedDate })}
          >
            <Plus size={20} aria-hidden="true" />
            新事件
          </button>
        </div>
      </header>

      {error ? <div className="notice error">{error}</div> : null}

      <section className="workspace">
        <div className="calendar-surface">
          <div className="calendar-toolbar">
            <button
              className="icon-button"
              type="button"
              title="上个月"
              onClick={() => setCurrentMonth(addMonths(currentMonth, -1))}
            >
              <ChevronLeft size={20} aria-hidden="true" />
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                const today = new Date();
                setCurrentMonth(startOfMonth(today));
                setSelectedDate(toDateKey(today));
              }}
            >
              今天
            </button>
            <button
              className="icon-button"
              type="button"
              title="下个月"
              onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
            >
              <ChevronRight size={20} aria-hidden="true" />
            </button>
          </div>

          <CalendarGrid
            currentMonth={currentMonth}
            selectedDate={selectedDate}
            eventsByDate={eventsByDate}
            onSelectDate={setSelectedDate}
          />
        </div>

        <aside className="side-panel">
          <section className="day-panel">
            <div className="panel-title-row">
              <div>
                <p className="eyebrow">当天事件</p>
                <h2>{formatDateTitle(selectedDate)}</h2>
              </div>
              <button
                className="icon-button"
                type="button"
                title="添加当天事件"
                onClick={() => setModalState({ mode: "create", date: selectedDate })}
              >
                <Plus size={18} aria-hidden="true" />
              </button>
            </div>

            {isLoading ? <p className="empty-state">正在加载事件...</p> : null}
            {!isLoading && selectedEvents.length === 0 ? (
              <p className="empty-state">这一天还没有事件。</p>
            ) : null}

            <div className="event-list">
              {selectedEvents.map((eventItem) => (
                <button
                  className="event-row"
                  type="button"
                  key={`${eventItem.series_id || eventItem.id}-${eventItem.start_time}`}
                  onClick={() => setModalState({ mode: "edit", event: eventItem })}
                >
                  <span>{formatTimeRange(eventItem)}</span>
                  <strong>{eventItem.title}</strong>
                  {eventItem.is_recurring ? <em>{recurrenceLabels[eventItem.recurrence_type]}</em> : null}
                </button>
              ))}
            </div>
          </section>

          <ChatPanel token={token} onUnauthorized={onLogout} onCommandComplete={loadEvents} />
        </aside>
      </section>

      {modalState ? (
        <EventModal
          state={modalState}
          onClose={() => setModalState(null)}
          onSave={handleSaveEvent}
          onDelete={handleDeleteEvent}
        />
      ) : null}
    </main>
  );
}

function CalendarGrid({ currentMonth, selectedDate, eventsByDate, onSelectDate }) {
  const days = getCalendarDays(currentMonth);
  const weekdays = ["一", "二", "三", "四", "五", "六", "日"];
  const todayKey = toDateKey(new Date());
  const currentMonthNumber = currentMonth.getMonth();

  return (
    <div className="calendar-grid">
      {weekdays.map((weekday) => (
        <div className="weekday" key={weekday}>
          {weekday}
        </div>
      ))}

      {days.map((day) => {
        const dateKey = toDateKey(day);
        const dateEvents = eventsByDate[dateKey] || [];
        const isOutside = day.getMonth() !== currentMonthNumber;
        const isSelected = dateKey === selectedDate;
        const isToday = dateKey === todayKey;

        return (
          <div
            className={[
              "day-cell",
              isOutside ? "outside" : "",
              isSelected ? "selected" : "",
              isToday ? "today" : "",
            ].join(" ")}
            key={dateKey}
            role="button"
            tabIndex={0}
            onClick={() => onSelectDate(dateKey)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectDate(dateKey);
              }
            }}
          >
            <span className="day-number">{day.getDate()}</span>
            <div className="day-events">
              {dateEvents.map((eventItem) => (
                <span className="event-chip" key={`${eventItem.id}-${eventItem.start_time}`}>
                  {eventItem.title}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ChatPanel({ token, onUnauthorized, onCommandComplete }) {
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const stopTimerRef = useRef(null);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "你好，我会在这里显示语音或文字指令的结果。" },
  ]);
  const [recordingMode, setRecordingMode] = useState(null);
  const [recordedAudio, setRecordedAudio] = useState(null);
  const [isProcessingAudio, setIsProcessingAudio] = useState(false);
  const [isTextInputOpen, setIsTextInputOpen] = useState(false);
  const [textCommand, setTextCommand] = useState("");

  useEffect(() => {
    return () => {
      window.clearTimeout(stopTimerRef.current);
      if (mediaRecorderRef.current?.state === "recording") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const startRecording = async (mode) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      });

      mediaRecorder.addEventListener("stop", () => {
        const mimeType = mediaRecorder.mimeType || "audio/webm";
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        stream.getTracks().forEach((track) => track.stop());
        setRecordedAudio({
          blob: audioBlob,
          mode,
          mimeType,
          recordedAt: new Date(),
        });
        setRecordingMode(null);
        processRecordedAudio(audioBlob, mimeType, mode);
      });

      mediaRecorder.start();
      setRecordingMode(mode);
      setRecordedAudio(null);
      setMessages((current) => [
        ...current,
        { role: "assistant", text: mode === "short" ? "按住录音中，松开后发送。" : "长录音开始，再次点击可停止。" },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: "assistant", text: `无法开始录音：${error.message}` },
      ]);
    }
  };

  const stopRecording = () => {
    window.clearTimeout(stopTimerRef.current);
    const recorder = mediaRecorderRef.current;

    if (recorder?.state === "recording") {
      recorder.stop();
    }
  };

  const handleLongRecordingButton = () => {
    const mode = "long";

    if (recordingMode === mode) {
      stopRecording();
      return;
    }

    if (recordingMode) {
      setMessages((current) => [
        ...current,
        { role: "assistant", text: "请先停止当前录音。" },
      ]);
      return;
    }

    startRecording(mode);
  };

  const handleShortRecordingStart = () => {
    if (recordingMode || isProcessingAudio) {
      return;
    }

    startRecording("short");
  };

  const handleShortRecordingEnd = () => {
    if (recordingMode === "short") {
      stopRecording();
    }
  };

  const processRecordedAudio = async (audioBlob, mimeType, mode) => {
    const label = mode === "short" ? "短录音" : "长录音";
    setIsProcessingAudio(true);
    setMessages((current) => [
      ...current,
      { role: "user", text: `${label}已完成` },
      { role: "assistant", text: "正在发送录音到后端处理..." },
    ]);

    try {
      const transcribed = await transcribeAudio(audioBlob, mimeType, token);
      const commandResult = await runVoiceCommand(transcribed.text, token);
      await onCommandComplete();
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: commandResult.message || "后端处理完成，日历已刷新。",
          transcript: transcribed.text,
          result: commandResult,
        },
      ]);
    } catch (error) {
      if (error.status === 401) {
        onUnauthorized();
        return;
      }

      setMessages((current) => [
        ...current,
        { role: "assistant", text: `录音处理失败：${error.message}` },
      ]);
    } finally {
      setIsProcessingAudio(false);
    }
  };

  const submitTextCommand = async (event) => {
    event.preventDefault();
    const commandText = textCommand.trim();

    if (!commandText) {
      return;
    }

    setIsProcessingAudio(true);
    setTextCommand("");
    setMessages((current) => [
      ...current,
      { role: "user", text: commandText },
      { role: "assistant", text: "正在发送文字指令到后端处理..." },
    ]);

    try {
      const commandResult = await runVoiceCommand(commandText, token);
      await onCommandComplete();
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: commandResult.message || "后端处理完成，日历已刷新。",
          transcript: commandText,
          result: commandResult,
        },
      ]);
    } catch (error) {
      if (error.status === 401) {
        onUnauthorized();
        return;
      }

      setMessages((current) => [
        ...current,
        { role: "assistant", text: `文字指令处理失败：${error.message}` },
      ]);
    } finally {
      setIsProcessingAudio(false);
    }
  };

  return (
    <section className="chat-panel">
      <div className="panel-title-row">
        <div>
          <p className="eyebrow">Assistant</p>
          <h2>对话框</h2>
        </div>
      </div>

      <div className="message-list">
        {messages.map((message, index) => (
          <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
            <p>{message.text}</p>
            {message.transcript ? (
              <div className="voice-result-block">
                <span>识别文本</span>
                <strong>{message.transcript}</strong>
              </div>
            ) : null}
            {message.result ? <VoiceResultSummary result={message.result} /> : null}
          </div>
        ))}
      </div>

      <div className="input-actions">
        <button
          className={recordingMode === "short" ? "recording" : ""}
          type="button"
          title="短录音"
          aria-label={recordingMode === "short" ? "停止短录音" : "短录音"}
          disabled={isProcessingAudio}
          onMouseDown={handleShortRecordingStart}
          onMouseLeave={handleShortRecordingEnd}
          onMouseUp={handleShortRecordingEnd}
          onTouchEnd={handleShortRecordingEnd}
          onTouchStart={handleShortRecordingStart}
        >
          <Mic size={20} aria-hidden="true" />
        </button>
        <button
          className={recordingMode === "long" ? "recording" : ""}
          type="button"
          title={recordingMode === "long" ? "停止长录音" : "长录音"}
          aria-label={recordingMode === "long" ? "停止长录音" : "长录音"}
          disabled={isProcessingAudio}
          onClick={handleLongRecordingButton}
        >
          <RecordIcon isRecording={recordingMode === "long"} />
        </button>
        <button
          type="button"
          title="键盘输入"
          aria-label="键盘输入"
          disabled={isProcessingAudio}
          onClick={() => setIsTextInputOpen((isOpen) => !isOpen)}
        >
          <Keyboard size={20} aria-hidden="true" />
        </button>
      </div>

      {isTextInputOpen ? (
        <form className="text-command-form" onSubmit={submitTextCommand}>
          <input
            aria-label="文字指令"
            value={textCommand}
            onChange={(event) => setTextCommand(event.target.value)}
            placeholder="输入日程指令"
          />
          <button type="submit" aria-label="发送文字指令" disabled={isProcessingAudio || !textCommand.trim()}>
            <Send size={18} aria-hidden="true" />
          </button>
        </form>
      ) : null}

      {recordedAudio ? (
        <p className="recording-status">
          最近录音：{recordedAudio.mode === "short" ? "短录音" : "长录音"}，
          {Math.max(1, Math.round(recordedAudio.blob.size / 1024))} KB
          {isProcessingAudio ? "，处理中" : ""}
        </p>
      ) : null}
    </section>
  );
}

function RecordIcon({ isRecording }) {
  return (
    <span className="record-icon" aria-hidden="true">
      <span className={isRecording ? "record-stop" : "record-dot"} />
    </span>
  );
}

function VoiceResultSummary({ result }) {
  const relatedEvents = [...(result.events || []), ...(result.candidates || [])];

  return (
    <div className="voice-result-summary">
      <div className="result-meta">
        <span>{result.intent || "unknown"}</span>
        <span>{result.status || "unknown"}</span>
      </div>

      {relatedEvents.length > 0 ? (
        <div className="result-events">
          {relatedEvents.slice(0, 3).map((eventItem) => (
            <div className="result-event" key={`${eventItem.id}-${eventItem.start_time}`}>
              <strong>{eventItem.title}</strong>
              {eventItem.start_time ? <span>{formatVoiceResultTime(eventItem)}</span> : null}
            </div>
          ))}
          {relatedEvents.length > 3 ? <em>还有 {relatedEvents.length - 3} 个结果</em> : null}
        </div>
      ) : null}
    </div>
  );
}

function EventModal({ state, onClose, onSave, onDelete }) {
  const editingEvent = state.mode === "edit" ? state.event : null;
  const defaultStart = editingEvent
    ? toDatetimeLocal(editingEvent.start_time)
    : `${state.date || toDateKey(new Date())}T09:00`;
  const defaultEnd = editingEvent
    ? toDatetimeLocal(editingEvent.end_time)
    : `${state.date || toDateKey(new Date())}T10:00`;

  const [form, setForm] = useState({
    title: editingEvent?.title || "",
    start_time: defaultStart,
    end_time: defaultEnd,
    notes: editingEvent?.notes || "",
    recurrence_type: editingEvent?.recurrence_type || "none",
    recurrence_interval: editingEvent?.recurrence_interval || 1,
    recurrence_until: editingEvent?.recurrence_until ? toDatetimeLocal(editingEvent.recurrence_until) : "",
  });
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setIsSaving(true);

    try {
      const payload = {
        title: form.title,
        start_time: fromDatetimeLocal(form.start_time),
        end_time: fromDatetimeLocal(form.end_time),
        notes: form.notes || null,
        recurrence_type: form.recurrence_type,
        recurrence_interval: Number(form.recurrence_interval) || 1,
      };

      if (form.recurrence_type !== "none" && form.recurrence_until) {
        payload.recurrence_until = fromDatetimeLocal(form.recurrence_until);
      }

      await onSave(payload, editingEvent?.series_id || editingEvent?.id);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    setError("");
    setIsSaving(true);

    try {
      await onDelete(editingEvent.series_id || editingEvent.id);
    } catch (requestError) {
      setError(requestError.message);
      setIsSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="event-modal-title">
        <div className="modal-header">
          <h2 id="event-modal-title">{editingEvent ? "编辑事件" : "添加事件"}</h2>
          <button className="icon-button" type="button" title="关闭" onClick={onClose}>
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <form className="event-form" onSubmit={handleSubmit}>
          <label>
            标题
            <input
              value={form.title}
              onChange={(event) => updateField("title", event.target.value)}
              placeholder="例如：产品讨论"
              required
            />
          </label>
          <div className="field-grid">
            <label>
              开始时间
              <input
                type="datetime-local"
                value={form.start_time}
                onChange={(event) => updateField("start_time", event.target.value)}
                required
              />
            </label>
            <label>
              结束时间
              <input
                type="datetime-local"
                value={form.end_time}
                onChange={(event) => updateField("end_time", event.target.value)}
                required
              />
            </label>
          </div>
          <label>
            备注
            <textarea
              value={form.notes}
              onChange={(event) => updateField("notes", event.target.value)}
              placeholder="可选"
              rows={3}
            />
          </label>
          <div className="field-grid">
            <label>
              重复
              <select value={form.recurrence_type} onChange={(event) => updateField("recurrence_type", event.target.value)}>
                <option value="none">不重复</option>
                <option value="daily">每天</option>
                <option value="weekly">每周</option>
                <option value="monthly">每月</option>
              </select>
            </label>
            <label>
              间隔
              <input
                type="number"
                min={1}
                value={form.recurrence_interval}
                onChange={(event) => updateField("recurrence_interval", event.target.value)}
              />
            </label>
          </div>
          {form.recurrence_type !== "none" ? (
            <label>
              重复截止
              <input
                type="datetime-local"
                value={form.recurrence_until}
                onChange={(event) => updateField("recurrence_until", event.target.value)}
              />
            </label>
          ) : null}

          {error ? <p className="form-error">{error}</p> : null}

          <div className="modal-actions">
            {editingEvent ? (
              <button className="danger-button" type="button" disabled={isSaving} onClick={handleDelete}>
                <Trash2 size={17} aria-hidden="true" />
                删除
              </button>
            ) : null}
            <button className="primary-button" type="submit" disabled={isSaving}>
              <Save size={17} aria-hidden="true" />
              {isSaving ? "保存中..." : "保存"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

async function apiRequest(path, { method = "GET", body, token } = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) {
    return {};
  }

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(payload.error || "请求失败");
    error.status = response.status;
    throw error;
  }

  return payload;
}

async function transcribeAudio(audioBlob, mimeType, token) {
  const extension = mimeType.includes("mp4") ? "mp4" : "webm";
  const formData = new FormData();
  formData.append("file", audioBlob, `recording.${extension}`);

  const response = await fetch(`${API_BASE_URL}/api/transcriptions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(payload.error || "录音转写失败");
    error.status = response.status;
    throw error;
  }

  return payload;
}

function runVoiceCommand(text, token) {
  return apiRequest("/api/voice-command", {
    method: "POST",
    token,
    body: {
      text,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai",
    },
  });
}

function getMonthRange(monthDate) {
  const start = startOfMonth(monthDate);
  const end = addMonths(start, 1);
  return { start, end };
}

function getCalendarDays(monthDate) {
  const monthStart = startOfMonth(monthDate);
  const firstDay = new Date(monthStart);
  const mondayOffset = (firstDay.getDay() + 6) % 7;
  firstDay.setDate(firstDay.getDate() - mondayOffset);

  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(firstDay);
    day.setDate(firstDay.getDate() + index);
    return day;
  });
}

function groupEventsByDate(events) {
  return events.reduce((groups, eventItem) => {
    const key = toDateKey(new Date(eventItem.start_time));
    groups[key] = [...(groups[key] || []), eventItem];
    return groups;
  }, {});
}

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addMonths(date, amount) {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function toDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function toDatetimeLocal(value) {
  const date = new Date(value);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function fromDatetimeLocal(value) {
  return new Date(value).toISOString();
}

function formatMonthTitle(date) {
  return date.toLocaleDateString("zh-CN", { year: "numeric", month: "long" });
}

function formatDateTitle(dateKey) {
  return new Date(`${dateKey}T00:00:00`).toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  });
}

function formatTimeRange(eventItem) {
  const start = new Date(eventItem.start_time).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const end = new Date(eventItem.end_time).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${start} - ${end}`;
}

function formatVoiceResultTime(eventItem) {
  const start = new Date(eventItem.start_time).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  if (!eventItem.end_time) {
    return start;
  }

  const end = new Date(eventItem.end_time).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${start} - ${end}`;
}

createRoot(document.getElementById("root")).render(<App />);
