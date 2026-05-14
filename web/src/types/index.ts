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

export interface ThemeDef {
  id: ThemeId
  label: string
  scheme: 'dark' | 'light'
  c1: string
  c2: string
}

export interface AttachChip {
  name: string
  path?: string
  dir?: string
}

export interface ToolCard {
  _key: number
  name: string
  icon: string
  param: string
  time: string
  success: boolean
  detail: string
  open: boolean
}

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

export interface Conversation {
  id: string
  summary?: string
  label: string
  raw_label?: string
  meta: string
  msg_count?: number
}

export interface UserConfig {
  type: 'openai' | 'anthropic'
  apiStyle: string
  model: string
  baseUrl: string
  keyDraft: string
  think: boolean
  stream: boolean
  acceptTask: boolean
}

export interface LogEntry {
  _key: string | number
  text: string
  success: boolean
}

export interface Task {
  id: string
  type: string
  time: string
  command: string
  last_run?: string
}

export interface PlanStep {
  id: string
  status?: 'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed' | string
  description: string
  result?: string
  error?: string
}

export interface Plan {
  id: string
  title: string
  description?: string
  status?: string
  steps: PlanStep[]
}

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

export interface ContextMenuState {
  show: boolean
  id: string
  label: string
  x: number
  y: number
}

export interface AppStore {
  users: string[]
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
  profileName: string
  profileInfo: string
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
  toastText: string
  toastVisible: boolean
  menu: ContextMenuState
}

