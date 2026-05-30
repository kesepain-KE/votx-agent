/** 定义 ThemeId 类型。 */
export type ThemeId =
  | 'dark'
  | 'light'
  | 'cream'
  | 'slate'
  | 'matcha-cake'
  | 'coconut-mint'
  | 'taro-mousse'
  | 'blue-sakura'
  | 'strawberry-cake'
  | 'cool-blue-gray'
  | 'peach-oolong'
  | 'caramel-macchiato'
  | 'rose-lychee'
  | 'lavender-latte'
  | 'sea-salt-cheese'

/** 描述 ThemeDef 数据结构。 */
export interface ThemeDef {
  id: ThemeId
  label: string
  scheme: 'dark' | 'light'
  c1: string
  c2: string
}

/** 描述 AttachChip 数据结构。 */
export interface AttachChip {
  name: string
  path?: string
  dir?: string
}

/** 描述 ToolCard 数据结构。 */
export interface ToolCard {
  _key: number
  name: string
  icon: string
  param: string
  time: string
  success: boolean
  detail: string
  open: boolean
  log_id?: string
}

/** 描述 UsageInfo 数据结构。 */
export interface UsageInfo {
  _prompt: number
  _completion: number
  _cached: number
  input: string
  output: string
  hit: string
  hit_rate: string
  time: string
}

/** 描述 Message 数据结构。 */
export interface Message {
  id: number
  type: 'sys' | 'error' | 'warn' | 'msg'
  role?: 'user' | 'assistant'
  content: string
  maxRounds?: boolean
  images?: AttachChip[]
  _raw?: string
  streaming?: boolean
  think?: string
  thinkOpen?: boolean
  usage?: UsageInfo | null
  tools?: ToolCard[]
  copied?: boolean
}

/** 描述 Conversation 数据结构。 */
export interface Conversation {
  id: string
  summary?: string
  label: string
  raw_label?: string
  meta: string
  msg_count?: number
}

/** 能力模式。 */
export type CapabilityMode = 'auto' | 'manual'

/** 描述 CapabilitiesInfo 数据结构。 */
export interface CapabilitiesInfo {
  mode: CapabilityMode
  detected: string[]
  effective: string[]
  override: string[] | null
}

/** 描述 UserConfig 数据结构。 */
export interface UserConfig {
  type: 'openai' | 'anthropic'
  apiStyle: string
  model: string
  baseUrl: string
  keyDraft: string
  think: boolean
  stream: boolean
  acceptTask: boolean
  capabilitiesOverride: string[] | null
  visionModel: string
  audioTranscriptionModel: string
  imageGenerationModel: string
  speechGenerationModel: string
}

/** 描述 LogEntry 数据结构。 */
export interface LogEntry {
  _key: string | number
  id?: string
  text: string
  success: boolean
  result?: string | null
  resultLoading?: boolean
}

/** 描述 Task 数据结构。 */
export interface Task {
  id: string
  type: string
  time: string
  command: string
  last_run?: string
}

/** 描述 PlanStep 数据结构。 */
export interface PlanStep {
  id: string
  status?: 'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed' | string
  description: string
  result?: string
  error?: string
}

/** 描述 Plan 数据结构。 */
export interface Plan {
  id: string
  title: string
  description?: string
  status?: string
  steps: PlanStep[]
}

/** 描述 FileItem 数据结构。 */
export interface FileItem {
  name: string
  path: string
  size?: number
  mtime?: number
  dir?: 'file' | 'download' | 'knowledge' | 'global-knowledge' | string
  _key: string
  checked: boolean
  sizeStr: string
  mtimeStr: string
}

/** 描述 ContextMenuState 数据结构。 */
export interface ContextMenuState {
  show: boolean
  id: string
  label: string
  x: number
  y: number
}

/** 描述 UserInfo 数据结构。 */
export interface UserInfo {
  name: string
  provider_type: string
  model: string
}

/** 描述插件版本信息。 */
export interface PluginVersion {
  name: string
  version: string
}

/** 描述 AppStore 数据结构。 */
export interface AppStore {
  users: UserInfo[]
  selectedUser: string
  userActive: boolean
  selectErr: string
  theme: ThemeId
  themeMenu: boolean
  themeMenuPos: { x: number; y: number }
  refreshing: boolean
  dragging: boolean
  userScrolledUp: boolean
  dragCounter: number
  msgId: number
  toastTimer: number | undefined
  abortCtrl: AbortController | null
  running: boolean
  showToolCalls: boolean
  showThinking: boolean
  input: string
  attachChips: AttachChip[]
  messages: Message[]
  conversations: Conversation[]
  activeConv: string
  showConvManager: boolean
  isPreview: boolean
  previewConvId: string | null
  activeTab: 'overview' | 'debug' | 'status' | 'files'
  promptTab: 'system' | 'soul' | 'agent' | 'other'
  statusSubTab: 'logs' | 'tasks' | 'task-plans'
  config: UserConfig
  lastSavedConfig: Partial<UserConfig>
  stats: { messages: string; tools: string; size: string }
  frameworkVersion: string
  pluginVersions: PluginVersion[]
  profileName: string
  profileInfo: string
  avatarUrl: string
  chatTitle: string
  mainSub: string
  modelName: string
  promptData: Record<string, string>
  logs: LogEntry[]
  tasks: Task[]
  taskPlans: Plan[]
  files: FileItem[]
  activePlan: Plan | null
  planPhase: 'review' | 'executing' | 'completed' | 'paused' | null
  capabilitiesInfo: CapabilitiesInfo | null
  capabilitiesMode: CapabilityMode
  toastText: string
  toastVisible: boolean
  menu: ContextMenuState
}

/** 描述后端返回的归档对话原始数据。 */
export interface RawConversation {
  id: string
  summary?: string
  label?: string
  raw_label?: string
  msg_count?: number
  size?: number
  mtime?: number
}

/** 描述后端返回的原始消息数据。 */
export interface RawMessage {
  role: string
  content?: string
  reasoning_content?: string
  tool_calls?: Array<{
    function?: { name: string; arguments: string }
  }>
}

/** 描述 SSE 流事件的联合类型。 */
export type SSEEvent =
  | { type: 'tool_call'; name: string; args: unknown; elapsed: number; success: boolean }
  | { type: 'text_chunk' | 'thinking_chunk'; content: string }
  | { type: 'text_done' | 'thinking_done' | 'done' | 'deadlock_warning' | 'max_rounds' }
  | { type: 'text' | 'thinking' | 'error'; content: string }
  | { type: 'usage'; data: { prompt_tokens: number; completion_tokens: number; cached_tokens: number; total_elapsed_ms?: number; elapsed?: number } }
  | { type: 'plan_created'; plan_id: string; plan: Plan }
  | { type: 'plan_started' | 'plan_complete' | 'plan_pause' | 'plan_aborted'; plan_id: string }
  | { type: 'plan_step'; plan_id: string; step: PlanStep }

/** 描述后端返回的配置原始数据。 */
export interface RawConfig {
  error?: string
  provider?: {
    type: string
    api_style: string
    think: boolean
    stream: boolean
    model: string
    base_url: string
  }
  task_plan?: { accept_task: boolean }
}

/** 描述后端返回的工具日志原始数据。 */
export interface RawToolLog {
  id?: string
  tool_call_id?: string
  ts?: string
  success: boolean
  tool: string
  args?: Record<string, unknown>
}
