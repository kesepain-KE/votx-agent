/**
 * useAppActions — 所有业务逻辑集中在这里
 * App.tsx 和各子组件通过这个 hook 调用方法、读状态
 */
import { type ChangeEvent, type DragEvent, type KeyboardEvent, type MouseEvent, useCallback, useEffect, useMemo, useRef } from 'react'
import { api, jsonBody } from '@/api/client'
import { defaultPromptData, THEMES, useAppStore } from '@/store/useAppStore'
import type { AppStore, AttachChip, Conversation, FileItem, Message, Plan, PlanStep, RawConfig, RawConversation, RawMessage, RawToolLog, SSEEvent, Task, ThemeId, ToolCard, UsageInfo, UserInfo } from '@/types'
import { fmtMs, fmtSize, fmtTime, formatNumber, isImageFile } from '@/utils/format'

/* ── 纯函数 ── */

export function applyTheme(id: ThemeId): ThemeId {
  const theme = THEMES.find((x) => x.id === id) || THEMES[0]
  document.body.setAttribute('data-theme', theme.id)
  document.body.setAttribute('data-color-scheme', theme.scheme)
  try {
    localStorage.setItem('votx-webui-theme', theme.id)
  } catch {
    // ignore private mode
  }
  return theme.id
}

/** 处理 planStatusColor 相关逻辑。 */
export function planStatusColor(status?: string) {
  const m: Record<string, string> = {
    pending: 'var(--text-tertiary)',
    in_progress: 'var(--accent)',
    completed: '#4caf50',
    paused: '#ff9800',
    aborted: '#f44336',
    failed: '#f44336',
  }
  return m[status || ''] || 'var(--text-tertiary)'
}

/** 处理 planStatusLabel 相关逻辑。 */
export function planStatusLabel(status?: string) {
  const m: Record<string, string> = {
    pending: '待执行',
    in_progress: '执行中',
    completed: '已完成',
    paused: '已暂停',
    aborted: '已中止',
    failed: '失败',
  }
  return m[status || ''] || status || '-'
}

/** 处理 planStepIcon 相关逻辑。 */
export function planStepIcon(status?: string) {
  const m: Record<string, string> = {
    pending: '○',
    in_progress: '●',
    completed: '✓',
    skipped: '↷',
    failed: '×',
  }
  return m[status || ''] || '○'
}

/* ── 常量 ── */

export const COMMANDS = ['/clear', '/retry', '/help', '/stats', '/compress']
/** 导出 TABS 常量配置。 */
export const TABS = [
  { id: 'overview', label: '概览' },
  { id: 'debug', label: '调试' },
  { id: 'status', label: '状态' },
  { id: 'files', label: '文件' },
] as const
/** 导出 PROMPT_TABS 常量配置。 */
export const PROMPT_TABS = [
  { id: 'system', label: 'system' },
  { id: 'soul', label: 'soul' },
  { id: 'agent', label: 'agent' },
  { id: 'other', label: '其他' },
] as const

const UI_STATE_KEY = 'votx-webui-ui-state-v1'
const DRAFT_KEY = 'votx-webui-draft-v1'
const ACTIVE_TABS: AppStore['activeTab'][] = ['overview', 'debug', 'status', 'files']
const PROMPT_TAB_IDS: AppStore['promptTab'][] = ['system', 'soul', 'agent', 'other']
const STATUS_TAB_IDS: AppStore['statusSubTab'][] = ['logs', 'tasks', 'task-plans']

type PersistedUIState = Pick<AppStore,
  'selectedUser' | 'activeTab' | 'promptTab' | 'statusSubTab' | 'showToolCalls' | 'showThinking'
>

function readPersistedUIState(): Partial<PersistedUIState> {
  try {
    const raw = JSON.parse(localStorage.getItem(UI_STATE_KEY) || '{}') as Partial<PersistedUIState>
    const next: Partial<PersistedUIState> = {}
    if (typeof raw.selectedUser === 'string') next.selectedUser = raw.selectedUser
    if (raw.activeTab && ACTIVE_TABS.includes(raw.activeTab)) next.activeTab = raw.activeTab
    if (raw.promptTab && PROMPT_TAB_IDS.includes(raw.promptTab)) next.promptTab = raw.promptTab
    if (raw.statusSubTab && STATUS_TAB_IDS.includes(raw.statusSubTab)) next.statusSubTab = raw.statusSubTab
    if (typeof raw.showToolCalls === 'boolean') next.showToolCalls = raw.showToolCalls
    if (typeof raw.showThinking === 'boolean') next.showThinking = raw.showThinking
    return next
  } catch {
    return {}
  }
}

function writePersistedUIState(state: PersistedUIState) {
  try {
    localStorage.setItem(UI_STATE_KEY, JSON.stringify(state))
  } catch {
    // ignore private mode
  }
}

function readDraftInput() {
  try {
    return sessionStorage.getItem(DRAFT_KEY) || ''
  } catch {
    return ''
  }
}

function writeDraftInput(value: string) {
  try {
    if (value) sessionStorage.setItem(DRAFT_KEY, value)
    else sessionStorage.removeItem(DRAFT_KEY)
  } catch {
    // ignore private mode
  }
}

/* ── Hook ── */

export function useAppActions() {
  const state = useAppStore()
  const set = useAppStore.setState
  const get = useAppStore.getState
  const chatRef = useRef<HTMLDivElement>(null)
  const textRef = useRef<HTMLTextAreaElement>(null)
  const uploadRef = useRef<HTMLInputElement>(null)
  const stateHydratedRef = useRef(false)

  /** 获取下一条本地消息 ID 并同步回 store。 */
  function nextId() {
    const id = get().msgId
    set({ msgId: id + 1 })
    return id
  }

  /* ── 派生数据 ── */
  const profileInitial = (state.profileName || 'K').slice(0, 1).toUpperCase()
  const themeLabel = THEMES.find((x) => x.id === state.theme)?.label || '高级黑'
  const planDoneCount = state.activePlan?.steps.filter((s) => s.status === 'completed').length || 0
  const hasCompletedPlans = state.taskPlans.some((p) => p.status === 'completed' || p.status === 'aborted')
  const fileGroups = useMemo(() => {
    const upload = state.files.filter((f) => f.dir === 'file')
    const download = state.files.filter((f) => f.dir === 'download')
    const knowledgeUser = state.files.filter((f) => f.dir === 'knowledge')
    const knowledgeGlobal = state.files.filter((f) => f.dir === 'global-knowledge')
    return [
      { label: '下载文件', files: download },
      { label: '上传文件', files: upload },
      { label: '知识库（用户）', files: knowledgeUser },
      { label: '知识库（全局）', files: knowledgeGlobal },
    ].filter((g) => g.files.length)
  }, [state.files])

  /* ── 基础工具 ── */

  function toast(text: string) {
    set({ toastText: text, toastVisible: true })
    const prev = get().toastTimer
    if (prev !== undefined) window.clearTimeout(prev)
    const tid = window.setTimeout(() => set({ toastVisible: false }), 2200)
    set({ toastTimer: tid })
  }

  function scrollBottom(force = false) {
      if (!force && get().userScrolledUp) return
      window.requestAnimationFrame(() => {
        const el = chatRef.current
        if (el) el.scrollTop = el.scrollHeight
      })
    }

  function onChatScroll() {
    const el = chatRef.current
    if (!el) return
    set({ userScrolledUp: el.scrollHeight - el.scrollTop - el.clientHeight > 60 })
  }

  function autoResize() {
    window.requestAnimationFrame(() => {
      const el = textRef.current
      if (!el) return
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 150)}px`
    })
  }

  /* ── 消息操作 ── */

  function pushMessage(message: Message) {
      set({ messages: [...get().messages, message] })
    }

  function patchMessage(id: number, patch: Partial<Message> | ((m: Message) => Message)) {
      set({
        messages: get().messages.map((m) => {
          if (m.id !== id) return m
          return typeof patch === 'function' ? patch({ ...m, tools: m.tools ? [...m.tools] : undefined }) : { ...m, ...patch }
        }),
      })
    }

  function updateLastAssistant(mutator: (m: Message) => void) {
      const messages = get().messages
      const idx = [...messages].reverse().findIndex((m) => m.role === 'assistant')
      if (idx < 0) return null
      const realIdx = messages.length - 1 - idx
      const next = [...messages]
      const msg = { ...next[realIdx], tools: next[realIdx].tools ? [...next[realIdx].tools!] : [] }
      mutator(msg)
      next[realIdx] = msg
      set({ messages: next })
      return msg
    }

  function pushSysMsg(content: string) { pushMessage({ id: nextId(), type: 'sys', content }) }
  function pushError(content: string) { pushMessage({ id: nextId(), type: 'error', content }) }
  function pushWarn(content: string, maxRounds = false) { pushMessage({ id: nextId(), type: 'warn', content, maxRounds }) }

  function pushUserMsg(content: string, images: AttachChip[] = []) { pushMessage({ id: nextId(), type: 'msg', role: 'user', content, images }) }

  function startAssistantMsg() {
    const id = nextId()
    pushMessage({ id, type: 'msg', role: 'assistant', content: '', _raw: '', streaming: true, think: '', thinkOpen: true, usage: null, tools: [], copied: false })
    return id
  }

  function makeToolCard(name: string, args: unknown, elapsed?: number, success = true, log_id?: string, pending?: boolean, startTs?: number, toolCallId?: string, icon?: string): ToolCard {
    const param = JSON.stringify(args || {}).slice(0, 80)
    return { _key: nextId(), name, icon: icon || '🔧', param, time: elapsed ? `${elapsed.toFixed(1)}s` : '', success, detail: JSON.stringify(args || {}, null, 2), open: false, log_id, pending, startTs, toolCallId }
  }

  function createRunId() {
    try {
      return crypto.randomUUID()
    } catch {
      return `${Date.now()}-${Math.random().toString(36).slice(2)}`
    }
  }

  function calcHitRate(cached: number, prompt: number) {
    if (!prompt || prompt <= 0) return '-'
    return `${((cached / prompt) * 100).toFixed(1)}%`
  }

  function snapshotConfig() {
    const { config } = get()
    set({
      lastSavedConfig: { type: config.type, model: config.model, baseUrl: config.baseUrl, stream: config.stream, acceptTask: config.acceptTask, capabilitiesOverride: config.capabilitiesOverride, visionModel: config.visionModel, audioTranscriptionModel: config.audioTranscriptionModel, imageGenerationModel: config.imageGenerationModel, imageEditModel: config.imageEditModel, speechGenerationModel: config.speechGenerationModel, speechToSpeechModel: config.speechToSpeechModel, videoGenerationModel: config.videoGenerationModel },
    })
  }

  /* ── API 调用 ── */

  const loadUsers = useCallback(async () => {
    try {
      const payload = await api<unknown>('/api/users')
      const users = Array.isArray(payload) ? payload.filter((u): u is {name:string} => typeof u === 'object' && u !== null && 'name' in u) : []
      set((s) => ({ users: users as UserInfo[], selectedUser: s.selectedUser || users[0]?.name || '' }))
    } catch { /* ignore */ }
  }, [set])

  const resetUI = useCallback(() => {
    set({
      userActive: false, profileName: '未连接', profileInfo: '选择用户开始',
      chatTitle: '对话闭环与工具调用', mainSub: '选择用户后开始对话', modelName: '-',
      messages: [], conversations: [], showConvManager: false, logs: [], files: [],
      promptData: defaultPromptData, promptTab: 'system', attachChips: [],
      activePlan: null, planPhase: null,
    })
    void loadUsers()
  }, [set, loadUsers])

  const selectUser = useCallback(async () => {
    const selectedUser = get().selectedUser
    if (!selectedUser) return
    if (get().userActive) {
      await api('/api/disconnect', { method: 'POST' })
      resetUI()
    }
    try {
      const data = await api<{ ok?: boolean; user?: string; error?: string }>('/api/select-user', { method: 'POST', ...jsonBody({ user: selectedUser }) })
      if (data.error) { set({ selectErr: data.error }); return }
      const user = data.user || selectedUser
      set({
        userActive: true, selectErr: '', profileName: user, profileInfo: '已连接', avatarUrl: `/api/avatar?t=${Date.now()}`,
        chatTitle: `${user} · 对话`, mainSub: '输入消息开始对话', modelName: '-',
        messages: [], attachChips: [], activeConv: '__current__', isPreview: false, previewConvId: null,
      })
      await Promise.all([refreshConversations(), loadToolLogs(), loadTasks(), loadTaskPlans(), loadFileList(), loadSystemPrompt(), loadDebugConfig(), updateStats(), loadVersion()])
      toast(`已连接 ${user}`)
    } catch (error) {
      set({ selectErr: `连接失败: ${(error as Error).message}` })
    }
  }, [set, get, resetUI])

  const updateStats = useCallback(async () => {
    if (!get().userActive) return
    try {
      const d = await api<{ error?: string; msg_count?: number; tool_count?: number; file_size?: number; context_window?: { used: number; max: number } }>('/api/stats')
      if (!d.error) {
        set({ stats: { messages: `${d.msg_count || 0} 条`, tools: `${d.tool_count || 0} 次`, size: fmtSize(d.file_size || 0) } })
        if (d.context_window) {
          set({ contextWindow: d.context_window })
        }
      }
    } catch { /* ignore */ }
  }, [set, get])

  const refreshConversations = useCallback(async () => {
    if (!get().userActive) return
    try {
      const convs = await api<RawConversation[]>('/api/conversations')
      if (!Array.isArray(convs)) return
      set({
        conversations: convs.map((c) => ({
          id: c.id, summary: c.summary, label: c.label || c.raw_label || '', raw_label: c.raw_label,
          meta: `${c.msg_count || 0} 条 · ${fmtSize(c.size || 0)} · ${fmtTime(c.mtime || 0)}`, msg_count: c.msg_count,
        })),
      })
    } catch { /* ignore */ }
  }, [set, get])

  const renderMessages = useCallback(
    (messages: RawMessage[]) => {
      for (const raw of messages) {
        if (raw.role === 'system') continue
        if (raw.role === 'user') {
          pushUserMsg(raw.content || '', [])
        } else if (raw.role === 'assistant') {
          const id = startAssistantMsg()
          patchMessage(id, (msg) => {
            msg.streaming = false
            if (raw.tool_calls) {
              msg.tools = raw.tool_calls.map((tc: NonNullable<RawMessage["tool_calls"]>[number]) => {
                const name = tc.function?.name || 'unknown'
                let args = {}
                try { args = JSON.parse(tc.function?.arguments || '{}') } catch { /* keep empty */ }
                return makeToolCard(name, args, 0, true, (tc as any).log_id)
              })
            }
            if (raw.content) { msg.content = raw.content; msg._raw = '' }
            if (raw.reasoning_content && !get().isPreview) { msg.think = raw.reasoning_content; msg.thinkOpen = false }
            return msg
          })
        }
      }
    },
    [pushUserMsg, startAssistantMsg, patchMessage, get, makeToolCard],
  )

  const loadConversation = useCallback(
    async (c: Conversation | { id: '__current__' }) => {
      if (!get().userActive) return
      if (get().running) stopRun()
      set({ userScrolledUp: false })

      if (c.id === '__current__') {
        set({ isPreview: false, previewConvId: null, messages: [] })
        try {
          await api('/api/conversations/select', { method: 'POST', ...jsonBody({ id: '__current__' }) }).catch(() => undefined)
          const msgs = await api<RawMessage[]>('/api/messages')
          if (Array.isArray(msgs)) renderMessages(msgs)
          const profileName = get().profileName || ''
          set({ chatTitle: `${profileName} · ${(c as Conversation).summary || (c as Conversation).label || '当前对话'}`, activeConv: c.id })
          scrollBottom()
        } catch (error) { toast(`加载失败: ${(error as Error).message}`) }
        return
      }

      try {
        const data = await api<{ error?: string; messages?: RawMessage[]; id?: string }>('/api/conversations/select', { method: 'POST', ...jsonBody({ id: c.id }) })
        if (data.error) { toast(`加载失败: ${data.error}`); return }
        set({ isPreview: true, messages: [] })
        renderMessages(data.messages || [])
        set({ previewConvId: c.id, chatTitle: `${get().profileName || ''} · 预览: ${(c as Conversation).label || data.id || c.id}`, activeConv: c.id })
        pushSysMsg('📋 归档预览（只读），点击"从此对话继续"可恢复为当前对话')
        scrollBottom()
      } catch (error) { toast(`加载失败: ${(error as Error).message}`) }
    },
    [get, set, renderMessages, scrollBottom, toast, pushSysMsg],
  )

  const continueConversation = useCallback(async () => {
    const { isPreview, previewConvId } = get()
    if (!isPreview || !previewConvId) return
    if (!window.confirm('将当前对话自动归档后，加载此历史对话为当前对话，继续？')) return
    try {
      const data = await api<{ error?: string; msg_count?: number }>('/api/conversations/continue', { method: 'POST', ...jsonBody({ id: previewConvId }) })
      if (data.error) { toast(`继续失败: ${data.error}`); return }
      set({ isPreview: false, previewConvId: null, activeConv: '__current__', messages: [] })
      const msgs = await api<RawMessage[]>('/api/messages')
      if (Array.isArray(msgs)) renderMessages(msgs)
      set({ chatTitle: `${get().profileName || ''} · 当前对话` })
      pushSysMsg(`已恢复 ${data.msg_count || 0} 条历史消息为当前对话`)
      await refreshOverview()
      scrollBottom()
    } catch (error) { toast(`继续失败: ${(error as Error).message}`) }
  }, [get, set, renderMessages])

  const deleteConversation = useCallback(async (id: string) => {
    if (id === '__current__') { toast('不能删除当前对话'); return }
    if (!window.confirm('确认删除此对话？此操作不可撤销。')) return
    try {
      const d = await api<{ error?: string }>('/api/conversations/' + encodeURIComponent(id), { method: 'DELETE' })
      if (d.error) { toast(d.error); return }
      toast('已删除')
      await refreshOverview()
    } catch (error) { toast(`删除失败: ${(error as Error).message}`) }
  }, [])

  const renameConv = useCallback(async (c: Conversation) => {
    const current = c.id === '__current__' ? c.summary || '新对话' : c.label
    const next = window.prompt('输入新的对话名', current || c.label)
    if (!next?.trim()) return
    try {
      const d = await api<{ error?: string }>('/api/conversations/' + encodeURIComponent(c.id) + '/rename', { method: 'POST', ...jsonBody({ name: next.trim() }) })
      if (d.error) { toast(d.error); return }
      toast('已重命名')
      await refreshOverview()
    } catch (error) { toast(`重命名失败: ${(error as Error).message}`) }
  }, [])

  const openConvMenu = useCallback((event: MouseEvent, c: Conversation) => {
    event.preventDefault()
    set({ menu: { show: true, id: c.id, label: c.label, x: event.clientX, y: event.clientY } })
  }, [set])

  const renameConvFromMenu = useCallback(() => {
    const menu = get().menu
    const c = get().conversations.find((x) => x.id === menu.id)
    set({ menu: { ...menu, show: false } })
    if (c) void renameConv(c)
  }, [get, set, renameConv])

  const deleteConvFromMenu = useCallback(() => {
    const menu = get().menu
    set({ menu: { ...menu, show: false } })
    void deleteConversation(menu.id)
  }, [get, set, deleteConversation])

  const deleteAllConvs = useCallback(async () => {
    if (!window.confirm('删除全部归档对话？此操作不可撤销。')) return
    try {
      const d = await api<{ deleted?: number }>('/api/conversations', { method: 'DELETE' })
      toast(`已删除 ${d.deleted || 0} 个对话`)
      await refreshOverview()
    } catch (error) { toast(`删除失败: ${(error as Error).message}`) }
  }, [])

  const saveChat = useCallback(async () => {
    if (!get().userActive) return
    if (get().topStatusKind) return  // 有其他状态在跑，防重复
    set({ topStatusText: '正在保存对话...', topStatusKind: 'save' })
    try {
      const d = await api<{ content?: string }>('/api/command', { method: 'POST', ...jsonBody({ command: '/archive' }) })
      toast(d.content || '已保存')
      await refreshOverview()
    } catch { toast('保存失败') }
    finally { setTimeout(() => set({ topStatusText: '', topStatusKind: '' }), 500) }
  }, [get, set])

  const newChat = useCallback(async () => {
    if (!get().userActive) return
    if (get().topStatusKind) return  // 有其他状态在跑，防重复
    if (get().running) stopRun()
    set({ topStatusText: '正在创建新对话...', topStatusKind: 'new-chat' })
    try {
      const d = await api<{ content?: string }>('/api/command', { method: 'POST', ...jsonBody({ command: '/new' }) })
      set({ messages: [], isPreview: false, previewConvId: null, activeConv: '__current__', chatTitle: `${get().profileName || ''} · 新对话` })
      pushSysMsg(d.content || '已创建新对话')
      await refreshOverview()
      toast('新对话已创建')
    } catch { toast('创建失败') }
    finally { setTimeout(() => set({ topStatusText: '', topStatusKind: '' }), 500) }
  }, [get, set])

  const removeLastAIReply = useCallback(() => {
    const messages = get().messages
    let lastUserIdx = -1
    for (let i = messages.length - 1; i >= 0; i--) { if (messages[i].role === 'user') { lastUserIdx = i; break } }
    if (lastUserIdx >= 0) set({ messages: messages.slice(0, lastUserIdx + 1) })
  }, [get, set])

  const sendCommand = useCallback(async (cmd: string) => {
    if (!get().userActive) { toast('请先选择用户'); return }
    if (get().running || get().topStatusKind) { toast('请等待当前操作完成'); return }
    const isCompress = cmd === '/compress'
    if (isCompress) set({ topStatusText: '正在压缩上下文...', topStatusKind: 'compress' })
    try {
      const d = await api<{ error?: string; retry?: boolean; content?: string }>('/api/command', { method: 'POST', ...jsonBody({ command: cmd }) })
      if (d.error) { toast(d.error); return }
      if (d.retry && d.content) { removeLastAIReply(); await streamChat(d.content); return }
      if (cmd === '/clear' || cmd === '/new') set({ messages: [] })
      await refreshOverview()
      pushSysMsg(d.content || '命令已执行')
      scrollBottom()
    } catch (error) { toast(`命令失败: ${(error as Error).message}`) }
    finally {
      if (isCompress) window.setTimeout(() => set({ topStatusText: '', topStatusKind: '' }), 500)
    }
  }, [get, set, removeLastAIReply])

  const sendMessage = useCallback(async () => {
    const text = get().input.trim()
    if (!text || !get().userActive || get().running) return
    if (get().isPreview) { toast('归档预览模式下无法发送消息，请先点击"从此对话继续"'); return }
    const attachPaths = get().attachChips.map((c) => c.path).filter(Boolean)
    const imageInfos = get().attachChips.filter((c) => isImageFile(c.name))
    const fullMsg = attachPaths.length ? `${attachPaths.join('\n')}\n${text}` : text
    set({ userScrolledUp: false })
    pushUserMsg(fullMsg, imageInfos)
    set({ input: '', attachChips: [] })
    autoResize()
    scrollBottom(true)
    await streamChat(fullMsg)
    scrollBottom()
  }, [get, set])

  const streamEvents = useCallback(async (url: string, body: unknown) => {
    const reqStart = Date.now()
    let pendingUsage: UsageInfo | null = null

    const res = await fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: get().abortCtrl!.signal,
    })
    const ct = res.headers.get('Content-Type') || ''
    if (!res.ok) {
      let message = `请求失败 (${res.status})`
      let data: unknown = null
      try {
        data = ct.includes('application/json') ? await res.json() : await res.text()
        if (typeof data === 'object' && data !== null && 'error' in data) message = String((data as { error?: unknown }).error || message)
        else if (typeof data === 'string' && data.trim()) message = data.trim()
      } catch {
        // keep default message
      }
      if (res.status === 401) {
        window.dispatchEvent(new CustomEvent('votx-session-expired', { detail: { error: message } }))
      }
      throw new Error(message)
    }
    if (ct.includes('application/json')) {
      const data = await res.json()
      updateLastAssistant((msg) => { msg.streaming = false; msg.content = data.content || data.error || '' })
      scrollBottom()
      return
    }
    const reader = res.body?.getReader()
    if (!reader) throw new Error('响应体不可读')
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6)
        if (data === '{"type":"done"}') continue
        let ev: SSEEvent
        try { ev = JSON.parse(data) } catch { continue }
        switch (ev.type) {
          case 'tool_call_start':
            updateLastAssistant((msg) => {
              const card = makeToolCard(ev.name, ev.args, undefined, true, undefined, true, Date.now(), ev.tool_call_id, (ev as any).icon)
              msg.tools = [...(msg.tools || []), card]
            })
            break
          case 'tool_call':
            updateLastAssistant((msg) => {
              const tcId = (ev as any).tool_call_id
              const tools = [...(msg.tools || [])]
              if (tcId) {
                const idx = tools.findIndex((t) => t.toolCallId === tcId && t.pending)
                if (idx >= 0) {
                  tools[idx] = {
                    ...tools[idx],
                    pending: false,
                    success: ev.success,
                    time: ev.elapsed ? `${ev.elapsed.toFixed(1)}s` : '',
                    log_id: (ev as any).log_id,
                    detail: JSON.stringify(ev.args || {}, null, 2),
                  }
                  msg.tools = tools
                  return
                }
              }
              msg.tools = [...tools, makeToolCard(ev.name, ev.args, ev.elapsed, ev.success, (ev as any).log_id, false, undefined, tcId, (ev as any).icon)]
            })
            break
          case 'text_chunk':
            updateLastAssistant((msg) => { msg._raw = (msg._raw || '') + (ev.content || '') })
            break
          case 'text_done':
            updateLastAssistant((msg) => {
              msg.content = msg._raw || ''; msg.streaming = false
              if (pendingUsage) { pendingUsage.time = fmtMs(Date.now() - reqStart); pendingUsage.hit_rate = calcHitRate(pendingUsage._cached, pendingUsage._prompt); msg.usage = pendingUsage; pendingUsage = null }
            })
            break
          case 'text':
            updateLastAssistant((msg) => {
              msg.content = ev.content || ''; msg.streaming = false
              if (pendingUsage) { pendingUsage.time = fmtMs(Date.now() - reqStart); pendingUsage.hit_rate = calcHitRate(pendingUsage._cached, pendingUsage._prompt); msg.usage = pendingUsage; pendingUsage = null }
            })
            break
          case 'thinking_chunk':
            updateLastAssistant((msg) => { msg.think = (msg.think || '') + (ev.content || ''); msg.thinkOpen = true })
            break
          case 'thinking':
            updateLastAssistant((msg) => { msg.think = ev.content || ''; msg.thinkOpen = true })
            break
          case 'thinking_done': break
          case 'usage':
            if (!pendingUsage) pendingUsage = { _prompt: 0, _completion: 0, _cached: 0, input: '', output: '', hit: '', time: '', hit_rate: '...' }
            pendingUsage._prompt += ev.data?.prompt_tokens || 0; pendingUsage._completion += ev.data?.completion_tokens || 0; pendingUsage._cached += ev.data?.cached_tokens || 0
            pendingUsage.input = formatNumber(pendingUsage._prompt); pendingUsage.output = formatNumber(pendingUsage._completion); pendingUsage.hit = formatNumber(pendingUsage._cached)
            pendingUsage.time = fmtMs(ev.data?.total_elapsed_ms || ev.data?.elapsed || 0)
            break
          case 'error': pushError(ev.content || '未知错误'); break
          case 'deadlock_warning': pushWarn('同命令连败 3 次，已提示 LLM 换思路'); break
          case 'max_rounds': pushWarn('已达到最大工具调用轮数', true); break
          case 'plan_created':
            if (ev.plan) { const a = get().activePlan; if (a && a.id === ev.plan_id) set({ activePlan: { ...a, ...ev.plan } }); else set({ activePlan: ev.plan, planPhase: 'review' }); void loadTaskPlans() }
            break
          case 'plan_started':
            if (get().activePlan?.id === ev.plan_id) set({ activePlan: { ...get().activePlan!, status: 'in_progress' }, planPhase: 'executing' })
            break
          case 'plan_step':
            if (ev.step) updatePlanStep(ev.plan_id, ev.step)
            break
          case 'plan_complete':
            if (get().activePlan?.id === ev.plan_id) { set({ activePlan: { ...get().activePlan!, status: 'completed' }, planPhase: 'completed' }); void loadTaskPlans() }
            break
          case 'plan_pause':
            if (get().activePlan?.id === ev.plan_id) { set({ activePlan: { ...get().activePlan!, status: 'paused' }, planPhase: 'paused' }); void loadTaskPlans() }
            break
          case 'plan_aborted':
            if (get().activePlan?.id === ev.plan_id) { set({ activePlan: null, planPhase: null }); void loadTaskPlans() }
            break
          case 'ui_status':
            set({ topStatusText: ev.content || '处理中...', topStatusKind: 'compress' })
            break
          case 'ui_status_clear':
            setTimeout(() => set({ topStatusText: '', topStatusKind: '' }), 500)
            break
        }
      }
      scrollBottom()
    }
  }, [get, set, updateLastAssistant, scrollBottom, pushError, pushWarn, makeToolCard, updatePlanStep, calcHitRate, fmtMs, formatNumber])

  const streamChat = useCallback(async (message: string) => {
    const runId = createRunId()
    set({ userScrolledUp: false, running: true, abortCtrl: new AbortController(), currentRunId: runId })
    startAssistantMsg()
    try {
      await streamEvents('/api/chat', { message, run_id: runId })
    } catch (error) {
      if ((error as Error).name !== 'AbortError') pushError(`连接错误: ${(error as Error).message}`)
    } finally {
      const activeRunId = get().currentRunId
      if (activeRunId === runId) {
        set({ running: false, abortCtrl: null, currentRunId: null })
        updateLastAssistant((msg) => { msg.streaming = false })
        scrollBottom(); void refreshOverview()
        window.requestAnimationFrame(() => textRef.current?.focus())
      } else if (!get().running) {
        updateLastAssistant((msg) => { msg.streaming = false })
        scrollBottom(); void refreshOverview()
        window.requestAnimationFrame(() => textRef.current?.focus())
      }
    }
  }, [get, set, streamEvents, startAssistantMsg, updateLastAssistant, scrollBottom, pushError])

  const streamPlanRun = useCallback(async (planId: string) => {
    const runId = createRunId()
    set({ running: true, abortCtrl: new AbortController(), currentRunId: runId })
    startAssistantMsg()
    try {
      await streamEvents(`/api/task-plan/${encodeURIComponent(planId)}/approve-run`, { run_id: runId })
    } catch (error) {
      if ((error as Error).name !== 'AbortError') pushError(`连接错误: ${(error as Error).message}`)
    } finally {
      const activeRunId = get().currentRunId
      if (activeRunId === runId) {
        set({ running: false, abortCtrl: null, currentRunId: null })
        updateLastAssistant((msg) => { msg.streaming = false })
        scrollBottom(); void refreshOverview()
        window.requestAnimationFrame(() => textRef.current?.focus())
      } else if (!get().running) {
        updateLastAssistant((msg) => { msg.streaming = false })
        scrollBottom(); void refreshOverview()
        window.requestAnimationFrame(() => textRef.current?.focus())
      }
    }
  }, [get, set, streamEvents, startAssistantMsg, updateLastAssistant, scrollBottom, pushError])

  function updatePlanStep(planId: string, step: PlanStep) {
    const active = get().activePlan
    if (active && active.id === planId) {
      const nextSteps = active.steps.map((s) => (s.id === step.id ? { ...s, ...step } : s))
      const shouldRun = get().planPhase === 'review' && (step.status === 'in_progress' || step.status === 'completed')
      set({ activePlan: { ...active, steps: nextSteps }, planPhase: shouldRun ? 'executing' : get().planPhase })
    }
    set({ taskPlans: get().taskPlans.map((p) => p.id === planId ? { ...p, steps: p.steps.map((s) => (s.id === step.id ? { ...s, ...step } : s)) } : p) })
  }

  function stopRun() {
    const ctrl = get().abortCtrl
    const runId = get().currentRunId
    if (ctrl) {
      ctrl.abort()
      set({ abortCtrl: null, running: false, currentRunId: null })
      updateLastAssistant((msg) => { msg.streaming = false })
      if (runId) {
        void api('/api/chat/stop', { method: 'POST', ...jsonBody({ run_id: runId }) }).catch(() => undefined)
      }
      toast('已停止运行')
    }
  }

  const continueAfterMaxRounds = useCallback(async () => {
    if (!get().userActive || get().running) return
    await streamChat('继续')
  }, [get, streamChat])

  const copyMsg = useCallback((message: Message) => {
    const text = (message.content || '').trim()
    navigator.clipboard.writeText(text).then(() => { patchMessage(message.id, { copied: true }); window.setTimeout(() => patchMessage(message.id, { copied: false }), 1500) }).catch(() => undefined)
    toast('已复制')
  }, [])

  const removeAttach = useCallback((index: number) => set({ attachChips: get().attachChips.filter((_f, i) => i !== index) }), [set, get])

  const guideFile = useCallback((file: FileItem) => {
    set({ attachChips: [...get().attachChips, { name: file.name, path: file.path, dir: file.dir || 'file' }] })
    window.requestAnimationFrame(() => textRef.current?.focus())
    toast(`已引用 ${file.path}`)
  }, [set, get])

  const onUploadFiles = useCallback((event: ChangeEvent<HTMLInputElement>) => { void uploadFiles(event.target.files); event.target.value = '' }, [])

  const uploadFiles = useCallback(async (fileList: FileList | File[] | null, forceDir = 'file') => {
    if (!fileList?.length || !get().userActive) return
    const form = new FormData()
    Array.from(fileList).forEach((file) => form.append('files', file))
    try {
      const res = await fetch(`/api/upload?dir=${forceDir}`, { method: 'POST', credentials: 'include', body: form })
      const data = await res.json()
      if (data.ok && data.files?.length) {
        set({ attachChips: [...get().attachChips, ...data.files.map((f: {name:string;path:string;dir?:string}) => ({ name: f.name, path: f.path, dir: f.dir || forceDir }))] })
        toast(`已上传 ${data.files.map((f: {name:string;path:string;dir?:string}) => f.name).join(', ')}`)
      }
      await loadFileList()
    } catch { toast('上传失败') }
  }, [set, get])

  const onDragEnter = useCallback(() => set({ dragCounter: get().dragCounter + 1, dragging: true }), [set, get])
  const onDragLeave = useCallback(() => { const next = Math.max(0, get().dragCounter - 1); set({ dragCounter: next, dragging: next > 0 }) }, [set, get])
  const onDrop = useCallback((event: DragEvent) => { set({ dragCounter: 0, dragging: false }); if (!get().userActive) { toast('请先选择用户'); return }; if (event.dataTransfer.files.length) void uploadFiles(event.dataTransfer.files) }, [set, get, uploadFiles])

  const onPaste = useCallback((event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = event.clipboardData?.items; if (!items) return
    const files: File[] = []; Array.from(items).forEach((item) => { if (item.kind === 'file') { const file = item.getAsFile(); if (file) files.push(file) } })
    if (files.length) { event.preventDefault(); void uploadFiles(files) }
  }, [uploadFiles])

  const loadFileList = useCallback(async () => {
    if (!get().userActive) return
    try {
      const [r1, r2, r3, r4] = await Promise.all([api<Array<{name:string;path:string;size?:number;mtime?:number}>>('/api/files?dir=file'), api<Array<{name:string;path:string;size?:number;mtime?:number}>>('/api/files?dir=download'), api<Array<{name:string;path:string;size?:number;mtime?:number}>>('/api/files?dir=knowledge'), api<Array<{name:string;path:string;size?:number;mtime?:number}>>('/api/files?dir=global-knowledge')])
      const normalize = (items: Array<{name:string;path:string;size?:number;mtime?:number}>, dir: string, prefix: string): FileItem[] => (Array.isArray(items) ? items : []).map((f) => ({ ...f, dir, _key: `${prefix}-${f.path || f.name}`, checked: false, sizeStr: fmtSize(f.size || 0), mtimeStr: fmtTime(f.mtime || 0) }))
      set({ files: [...normalize(r1, 'file', 'f'), ...normalize(r2, 'download', 'd'), ...normalize(r3, 'knowledge', 'k'), ...normalize(r4, 'global-knowledge', 'gk')] })
    } catch { /* ignore */ }
  }, [set, get])

  const downloadFile = useCallback((file: FileItem) => window.open(`/api/files/download/${encodeURIComponent(file.name)}?dir=${file.dir || 'file'}`, '_blank'), [])

  const deleteFile = useCallback(async (file: FileItem) => {
    try {
      const data = await api<{ ok?: boolean; error?: string }>(`/api/files/${encodeURIComponent(file.name)}?dir=${file.dir || 'file'}`, { method: 'DELETE' })
      if (data.ok) { set({ files: get().files.filter((x) => x._key !== file._key) }); toast('文件已删除') } else { toast(data.error || '删除失败') }
    } catch (error) { toast(`删除失败: ${(error as Error).message}`) }
  }, [set, get])

  const deleteAllFiles = useCallback(async () => {
    if (!window.confirm('删除全部上传和下载文件？此操作不可撤销。')) return
    let total = 0
    try {
      for (const dir of ['file', 'download']) { const data = await api<{ deleted?: number }>(`/api/files?dir=${dir}`, { method: 'DELETE' }); total += data.deleted || 0 }
      set({ files: get().files.filter((f) => f.dir !== 'file' && f.dir !== 'download') })
      toast(`已删除 ${total} 个文件`)
    } catch (error) { toast(`删除失败: ${(error as Error).message}`) }
  }, [set, get])

  const deleteCheckedFiles = useCallback(async () => {
    const checked = get().files.filter((f) => f.checked)
    if (!checked.length) { toast('请先勾选要删除的文件'); return }
    const groups = checked.reduce<Record<string, string[]>>((acc, file) => { const dir = file.dir || 'file'; (acc[dir] = acc[dir] || []).push(file.name); return acc }, {})
    let total = 0
    try {
      for (const [dir, names] of Object.entries(groups)) { const data = await api<{ deleted?: number }>(`/api/files?dir=${dir}`, { method: 'DELETE', ...jsonBody({ files: names }) }); total += data.deleted || 0 }
      set({ files: get().files.filter((f) => !f.checked) }); toast(`已批量删除 ${total} 个文件`)
    } catch (error) { toast(`删除失败: ${(error as Error).message}`) }
  }, [get, set])

  const loadToolLogs = useCallback(async () => {
    if (!get().userActive) return
    try {
      const logs = await api<RawToolLog[]>('/api/tool-logs')
      if (!Array.isArray(logs) || !logs.length) { set({ logs: [] }); return }
      set({
        logs: logs.slice(-30).reverse().map((l, i) => {
          let ts = ''
          if (l.ts) { try { const d = new Date(l.ts); ts = Number.isNaN(d.getTime()) ? String(l.ts).replace('T', ' ').slice(0, 19) : d.toLocaleString('zh-CN') } catch { ts = String(l.ts).replace('T', ' ').slice(0, 19) } }
          return { _key: l.id || `${l.ts || ''}-${l.tool || 'tool'}-${i}`, id: l.id, text: `${ts} ${l.success ? '✓' : '×'} ${l.tool} ${JSON.stringify(l.args || {}).slice(0, 80)}`, success: !!l.success }
        }),
      })
    } catch { /* ignore */ }
  }, [set, get])

  const loadToolResult = useCallback(async (logId: string): Promise<string> => {
    try {
      const res = await api<{ result: string; tool: string; success: boolean }>(`/api/tool-results/${encodeURIComponent(logId)}`)
      return res?.result || ''
    } catch { return '' }
  }, [])

  const loadTasks = useCallback(async () => { if (!get().userActive) return; try { set({ tasks: (await api<Task[]>('/api/tasks')) || [] }) } catch { /* ignore */ } }, [set, get])

  const deleteTask = useCallback(async (taskId: string) => {
    if (!get().userActive) return; if (!window.confirm('确定删除此任务？')) return
    try { await api(`/api/tasks/${encodeURIComponent(taskId)}`, { method: 'DELETE' }); await loadTasks(); toast('任务已删除') } catch (error) { toast(`删除失败: ${(error as Error).message}`) }
  }, [get, loadTasks])

  const loadTaskPlans = useCallback(async () => { if (!get().userActive) return; try { set({ taskPlans: (await api<Plan[]>('/api/task-plan')) || [] }) } catch { /* ignore */ } }, [set, get])

  const clearCompletedPlans = useCallback(async () => {
    if (!get().userActive) return; if (!window.confirm('确定删除所有已完成/已中止的计划？')) return
    try { const data = await api<{ deleted?: number }>('/api/task-plan/clear-completed', { method: 'POST' }); toast(`已删除 ${data.deleted || 0} 个计划`); await loadTaskPlans() } catch (error) { toast(`删除失败: ${(error as Error).message}`) }
  }, [get, loadTaskPlans])

  const abortPlan = useCallback(async (planId: string) => {
    if (!get().userActive) return; if (!window.confirm('确定中止此计划？未完成的步骤将被跳过。')) return
    try { await api(`/api/task-plan/${encodeURIComponent(planId)}/abort`, { method: 'POST' }); if (get().activePlan?.id === planId) set({ activePlan: null, planPhase: null }); await loadTaskPlans(); toast('计划已中止') } catch (error) { toast(`中止失败: ${(error as Error).message}`) }
  }, [get, set, loadTaskPlans])

  const approvePlan = useCallback(async () => {
    const activePlan = get().activePlan; if (!activePlan) return
    if (get().running) { toast('当前正在执行中，请勿重复启动'); return }
    const steps = activePlan.steps.map((s, i) =>
      i === activePlan.steps.findIndex((x) => x.status === 'pending') ? { ...s, status: 'in_progress' } : s
    )
    set({ activePlan: { ...activePlan, status: 'in_progress', steps }, planPhase: 'executing' })
    toast('计划已批准，开始执行')
    await streamPlanRun(activePlan.id)
  }, [get, set, streamPlanRun])

  const rejectPlan = useCallback(async () => {
    const activePlan = get().activePlan; if (!activePlan) return
    try {
      await api(`/api/task-plan/${encodeURIComponent(activePlan.id)}/reject`, { method: 'POST' })
      set({ activePlan: null, planPhase: null })
      await loadTaskPlans()
      toast('计划已拒绝')
    } catch (error) { toast(`操作失败: ${(error as Error).message}`) }
  }, [get, set, loadTaskPlans])

  const modifyPlan = useCallback(() => { toast('请直接发送修改要求，例如"把第2步改成..."'); textRef.current?.focus() }, [])

  const exitAbortPlan = useCallback(async () => {
    const activePlan = get().activePlan; if (!activePlan) return; if (!window.confirm('确定退出并终止此计划？未完成的步骤将被跳过。')) return
    if (get().running) stopRun()
    try { await api(`/api/task-plan/${encodeURIComponent(activePlan.id)}/abort`, { method: 'POST' }); set({ activePlan: null, planPhase: null }); await loadTaskPlans(); toast('计划已终止') } catch (error) { toast(`操作失败: ${(error as Error).message}`) }
  }, [get, set, loadTaskPlans])

  const stopModifyPlan = useCallback(async () => {
    const activePlan = get().activePlan; if (!activePlan) return; if (get().running) stopRun()
    try { await api(`/api/task-plan/${encodeURIComponent(activePlan.id)}/pause`, { method: 'POST' }); set({ activePlan: { ...activePlan, status: 'paused' }, planPhase: 'paused' }); toast('计划已暂停，请发送修改要求'); textRef.current?.focus() } catch (error) { toast(`操作失败: ${(error as Error).message}`) }
  }, [get, set])

  const continuePlan = useCallback(async () => {
    const activePlan = get().activePlan; if (!activePlan) return
    if (get().running) { toast('当前正在执行中，请勿重复启动'); return }
    set({ activePlan: { ...activePlan, status: 'in_progress' }, planPhase: 'executing' })
    toast('继续执行计划')
    await streamPlanRun(activePlan.id)
  }, [get, set, streamPlanRun])

  const exitPlan = useCallback(() => { set({ activePlan: null, planPhase: null }); toast('任务已退出') }, [set])

  const loadSystemPrompt = useCallback(async () => {
    if (!get().userActive) return
    try {
      const data = await api<{content:string;soul:string;agent:string;other:string;error?:string}>('/api/system-prompt')
      if (!data.error && data.content) set({ promptData: { system: data.content || '', soul: data.soul || '未找到 soul 定义文件', agent: data.agent || '未找到 AGENTS.md', other: data.other || 'Skill 摘要、持久记忆等\n\n在完整 prompt 中查看...' } })
    } catch { /* ignore */ }
  }, [set, get])

  const loadVersion = useCallback(async () => {
    try {
      const data = await api<{framework:{name:string;version:string};plugins:{name:string;version:string}[]}>('/api/version')
      if (data.framework) set({ frameworkVersion: `v${data.framework.version}` })
      if (Array.isArray(data.plugins)) set({ pluginVersions: data.plugins })
    } catch { /* ignore */ }
  }, [set])

  const loadDebugConfig = useCallback(async () => {
    if (!get().userActive) return
    try {
      const cfg = await api<RawConfig>('/api/config'); if (cfg.error) return
      const provider = cfg.provider; const rawType = provider?.type || 'votx'
      set((s) => ({
        config: { ...s.config, type: 'votx', stream: !!provider?.stream, acceptTask: !!(cfg.task_plan && cfg.task_plan.accept_task), model: provider?.model || '', baseUrl: provider?.base_url || '',
          capabilitiesOverride: (provider as Record<string,unknown>)?.capabilities_override as string[]|null ?? null,
          visionModel: (provider as Record<string,unknown>)?.vision_model as string || '',
          audioTranscriptionModel: (provider as Record<string,unknown>)?.audio_transcription_model as string || '',
          imageGenerationModel: (provider as Record<string,unknown>)?.image_generation_model as string || '',
          imageEditModel: (provider as Record<string,unknown>)?.image_edit_model as string || '',
          speechGenerationModel: (provider as Record<string,unknown>)?.speech_generation_model as string || '',
          speechToSpeechModel: (provider as Record<string,unknown>)?.speech_to_speech_model as string || '',
          videoGenerationModel: (provider as Record<string,unknown>)?.video_generation_model as string || '',
        },
        modelName: provider?.model || '-',
      }))
      snapshotConfig()
    } catch { /* ignore */ }
  }, [set, get])

  const saveConfigField = useCallback(async (key: string, value: unknown) => {
    if (!get().userActive) return
    try { await api('/api/config', { method: 'POST', ...jsonBody({ [key]: value }) }); if (key === 'model') set({ modelName: String(value || '-') }); toast('已保存') } catch { toast('保存失败') }
  }, [get, set])

  const toggleConfigSwitch = useCallback(async (key: 'stream' | 'accept_task') => {
    if (!get().userActive) { toast('请先选择用户'); return }
    const prop = key === 'accept_task' ? 'acceptTask' : key; const current = get().config[prop]
    set((s) => ({ config: { ...s.config, [prop]: !current } }))
    try { await api('/api/config', { method: 'POST', ...jsonBody({ [key]: !current }) }); toast(`${!current ? '已开启' : '已关闭'}${key === 'accept_task' ? '自动执行任务计划' : '流式输出'}`) } catch { set((s) => ({ config: { ...s.config, [prop]: current } })); toast('保存失败') }
  }, [get, set])

  const saveAllConfig = useCallback(async () => {
    if (!get().userActive) { toast('请先选择用户'); return }
    const { config } = get()
    const payload: Record<string, unknown> = { type: config.type, model: config.model, base_url: config.baseUrl }
    if (config.keyDraft.trim()) payload.api_key = config.keyDraft.trim()
    try { await api('/api/config', { method: 'POST', ...jsonBody(payload) }); snapshotConfig(); set((s) => ({ config: { ...s.config, keyDraft: '' } })); toast('配置已保存') } catch { toast('保存失败') }
  }, [get, set])

  const applyConfig = useCallback(async () => {
    if (!get().userActive) { toast('请先选择用户'); return }; await loadDebugConfig(); snapshotConfig(); toast('配置已从磁盘重新加载')
  }, [get, loadDebugConfig])

  const reloadAgent = useCallback(async () => {
    if (!get().userActive) { toast('请先选择用户'); return }
    try { const res = await api<{ ok?: boolean; error?: string; reloaded?: string[] }>('/api/reload', { method: 'POST' }); if (res.ok) toast(`已重载 ${(res.reloaded || []).join(', ')}`); else if (res.error) toast(res.error) } catch { toast('重载失败') }
  }, [get])

  const fetchCapabilities = useCallback(async () => {
    if (!get().userActive) return
    try {
      const res = await api<import('@/types').CapabilitiesInfo>('/api/provider-capabilities')
      set({ capabilitiesInfo: res, capabilitiesMode: res.mode })
    } catch { /* ignore */ }
  }, [get])

  const setCapabilitiesMode = useCallback((mode: import('@/types').CapabilityMode) => {
    set({ capabilitiesMode: mode })
  }, [])

  const toggleCapability = useCallback((cap: string) => {
    const info = get().capabilitiesInfo
    if (!info) return
    const current = info.override ?? info.effective
    const next = current.includes(cap)
      ? current.filter((c: string) => c !== cap)
      : [...current, cap]
    set({ capabilitiesInfo: { ...info, override: next } })
  }, [get])

  const saveCapabilities = useCallback(async () => {
    const { capabilitiesMode, capabilitiesInfo } = get()
    if (!capabilitiesInfo) return
    try {
      if (capabilitiesMode === 'auto') {
        await api('/api/config', { method: 'POST', ...jsonBody({ capabilities_override: null }) })
      } else {
        const override = capabilitiesInfo.override || []
        await api('/api/config', { method: 'POST', ...jsonBody({ capabilities_override: override }) })
      }
      toast('能力配置已保存，正在重载...')
      await reloadAgent()
    } catch { toast('保存失败') }
  }, [get])

  const restoreConfig = useCallback(() => {
    if (!get().userActive) { toast('请先选择用户'); return }
    const last = get().lastSavedConfig; if (!last.model && !last.baseUrl && !last.type) { toast('没有可恢复的保存状态'); return }
    set((s) => ({ config: { ...s.config, type: last.type || 'votx', model: last.model || '', baseUrl: last.baseUrl || '', stream: 'stream' in last ? !!last.stream : s.config.stream, acceptTask: 'acceptTask' in last ? !!last.acceptTask : s.config.acceptTask, capabilitiesOverride: ('capabilitiesOverride' in last ? last.capabilitiesOverride ?? null : s.config.capabilitiesOverride), visionModel: 'visionModel' in last ? (last.visionModel || '') : s.config.visionModel, audioTranscriptionModel: 'audioTranscriptionModel' in last ? (last.audioTranscriptionModel || '') : s.config.audioTranscriptionModel, imageGenerationModel: 'imageGenerationModel' in last ? (last.imageGenerationModel || '') : s.config.imageGenerationModel, imageEditModel: 'imageEditModel' in last ? (last.imageEditModel || '') : s.config.imageEditModel, speechGenerationModel: 'speechGenerationModel' in last ? (last.speechGenerationModel || '') : s.config.speechGenerationModel, speechToSpeechModel: 'speechToSpeechModel' in last ? (last.speechToSpeechModel || '') : s.config.speechToSpeechModel, videoGenerationModel: 'videoGenerationModel' in last ? (last.videoGenerationModel || '') : s.config.videoGenerationModel } }))
    toast('已恢复到上次保存状态')
  }, [get, set])

  const refreshOverview = useCallback(async () => {
    set({ refreshing: true })
    try { await Promise.all([updateStats(), loadSystemPrompt(), loadDebugConfig(), loadToolLogs(), loadFileList(), refreshConversations(), loadVersion()]); toast('已刷新') } catch { /* ignore */ }
    window.setTimeout(() => set({ refreshing: false }), 600)
  }, [set, updateStats, loadSystemPrompt, loadDebugConfig, loadToolLogs, loadFileList, refreshConversations, loadVersion])

  const restoreSession = useCallback(async () => {
    try {
      const session = await api<{ active?: boolean; user?: string }>('/api/session'); if (!session.active) return
      set({ userActive: true, selectedUser: session.user || get().selectedUser, profileName: session.user || '已连接用户', profileInfo: '已连接', avatarUrl: `/api/avatar?t=${Date.now()}`, chatTitle: `${session.user || ''} · 对话`, mainSub: '输入消息开始对话', activeConv: '__current__', isPreview: false, previewConvId: null })
      await Promise.all([refreshConversations(), loadToolLogs(), loadTasks(), loadTaskPlans(), loadFileList(), loadSystemPrompt(), loadDebugConfig(), updateStats(), loadVersion()])

      const activePlan = get().taskPlans.find((p) => p.status === 'in_progress' || p.status === 'paused')
        || get().taskPlans.find((p) => p.status === 'pending')
        || null
      if (activePlan) {
        const phase: AppStore['planPhase'] = activePlan.status === 'paused' ? 'paused' : activePlan.status === 'pending' ? 'review' : 'executing'
        set({ activePlan, planPhase: phase })
      }

      let restoredPreview = false
      try {
        const preview = await api<{ preview?: boolean; id?: string }>('/api/conversations/preview-state')
        if (preview.preview && preview.id && preview.id !== '__current__') {
          const conv = get().conversations.find((c) => c.id === preview.id)
            || { id: preview.id, label: preview.id, summary: preview.id, meta: '', msg_count: 0 }
          await loadConversation(conv)
          restoredPreview = true
        }
      } catch { /* ignore */ }

      if (!restoredPreview) {
        try {
          const msgs = await api<RawMessage[]>('/api/messages')
          if (Array.isArray(msgs) && msgs.length) { set({ messages: [] }); renderMessages(msgs); scrollBottom() }
        } catch { /* ignore */ }
      }
    } catch { /* ignore */ }
  }, [set, get, renderMessages, refreshConversations, loadToolLogs, loadTasks, loadTaskPlans, loadFileList, loadSystemPrompt, loadDebugConfig, updateStats, loadVersion, loadConversation])

  const toggleThemeMenu = useCallback((event: MouseEvent<HTMLButtonElement>) => {
    const rect = event.currentTarget.getBoundingClientRect(); const menuW = 162; const menuH = 330; const gap = 8
    const x = Math.max(8, Math.min(window.innerWidth - menuW - 8, rect.right - menuW))
    const aboveY = rect.top - menuH - gap; const belowY = rect.bottom + gap
    const y = aboveY >= 8 ? aboveY : Math.min(window.innerHeight - menuH - 8, belowY)
    set({ themeMenuPos: { x, y: Math.max(8, y) }, themeMenu: !get().themeMenu })
  }, [set, get])

  const chooseTheme = useCallback((theme: ThemeId) => { set({ theme, themeMenu: false }) }, [set])

  const onTextareaKeyDown = useCallback((event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendMessage() } }, [sendMessage])

  /* ── Effects ── */

  useEffect(() => {
    const persistedUI = readPersistedUIState()
    const draftInput = readDraftInput()
    set((s) => ({ ...s, ...persistedUI, input: draftInput || s.input }))
    try { const saved = localStorage.getItem('votx-webui-theme') as ThemeId | null; if (saved && THEMES.some((t) => t.id === saved)) set({ theme: saved }); else applyTheme('dark') } catch { applyTheme('dark') }
    void loadUsers(); void restoreSession()
    window.setTimeout(() => { stateHydratedRef.current = true }, 0)
    const closeMenus = () => set((s) => ({ menu: { ...s.menu, show: false }, themeMenu: false }))
    const onSessionExpired = (event: Event) => {
      const detail = (event as CustomEvent<{ error?: string }>).detail
      get().abortCtrl?.abort()
      set({
        userActive: false,
        profileName: '未连接',
        profileInfo: '会话已失效，请重新选择用户',
        chatTitle: '对话闭环与工具调用',
        mainSub: '选择用户后开始对话',
        modelName: '-',
        running: false,
        abortCtrl: null,
        messages: [],
        conversations: [],
        logs: [],
        tasks: [],
        taskPlans: [],
        files: [],
        activePlan: null,
        planPhase: null,
      })
      toast(detail?.error || '访问令牌已失效，请通过 ?token=xxx URL 重新访问')
    }
    document.addEventListener('click', closeMenus)
    window.addEventListener('votx-session-expired', onSessionExpired)
    return () => {
      document.removeEventListener('click', closeMenus)
      window.removeEventListener('votx-session-expired', onSessionExpired)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { const applied = applyTheme(state.theme); if (applied !== state.theme) set({ theme: applied }) }, [set, state.theme])
  useEffect(() => { autoResize() }, [state.input])
  useEffect(() => {
    if (!stateHydratedRef.current) return
    writePersistedUIState({
      selectedUser: state.selectedUser,
      activeTab: state.activeTab,
      promptTab: state.promptTab,
      statusSubTab: state.statusSubTab,
      showToolCalls: state.showToolCalls,
      showThinking: state.showThinking,
    })
  }, [state.selectedUser, state.activeTab, state.promptTab, state.statusSubTab, state.showToolCalls, state.showThinking])
  useEffect(() => {
    if (!stateHydratedRef.current) return
    writeDraftInput(state.input)
  }, [state.input])

  return {
    /* state */ ...state,
    /* derived */ profileInitial, themeLabel, planDoneCount, hasCompletedPlans, fileGroups,
    /* refs */ chatRef, textRef, uploadRef,
    /* actions */
    toast, scrollBottom, onChatScroll, autoResize,
    pushMessage, patchMessage, updateLastAssistant,
    pushSysMsg, pushError, pushWarn, pushUserMsg, startAssistantMsg, makeToolCard, calcHitRate, snapshotConfig,
    loadUsers, resetUI, selectUser, updateStats, refreshConversations, renderMessages,
    loadConversation, continueConversation, deleteConversation, renameConv,
    openConvMenu, renameConvFromMenu, deleteConvFromMenu, deleteAllConvs,
    saveChat, newChat, sendCommand, removeLastAIReply, sendMessage, streamChat,
    updatePlanStep, stopRun, continueAfterMaxRounds, copyMsg,
    removeAttach, guideFile, onUploadFiles, uploadFiles,
    onDragEnter, onDragLeave, onDrop, onPaste,
    loadFileList, downloadFile, deleteFile, deleteAllFiles, deleteCheckedFiles,
    loadToolLogs, loadToolResult, loadTasks, deleteTask, loadTaskPlans, clearCompletedPlans,
    abortPlan, approvePlan, rejectPlan, modifyPlan, exitAbortPlan, stopModifyPlan, continuePlan, exitPlan,
    loadSystemPrompt, loadDebugConfig, loadVersion, saveConfigField, toggleConfigSwitch,
    saveAllConfig, applyConfig, reloadAgent, restoreConfig,
    fetchCapabilities, setCapabilitiesMode, toggleCapability, saveCapabilities,
    refreshOverview, restoreSession, toggleThemeMenu, chooseTheme, onTextareaKeyDown,
    streamPlanRun, streamEvents,
  }
}
