/** 描述 Props 数据结构。 */
import { useEffect, useState } from 'react'
import { useAppStore } from '@/store/useAppStore'
import type { AppStore, FileItem } from '@/types'
import { planStatusColor, planStatusLabel, planStepIcon, PROMPT_TABS } from '@/hooks/useAppActions'

/** 描述 Props 数据结构。 */
interface Props {
  toggleConfigSwitch: (key: 'stream' | 'accept_task') => Promise<void>
  saveConfigField: (key: string, value: unknown) => Promise<void>
  saveAllConfig: () => Promise<void>
  applyConfig: () => Promise<void>
  restoreConfig: () => void
  reloadAgent: () => Promise<void>
  loadToolLogs: () => Promise<void>
  loadToolResult: (logId: string) => Promise<string>
  loadTasks: () => Promise<void>
  deleteTask: (id: string) => Promise<void>
  loadTaskPlans: () => Promise<void>
  clearCompletedPlans: () => Promise<void>
  abortPlan: (id: string) => Promise<void>
  loadFileList: () => Promise<void>
  deleteAllFiles: () => Promise<void>
  deleteCheckedFiles: () => Promise<void>
  downloadFile: (f: FileItem) => void
  deleteFile: (f: FileItem) => Promise<void>
  guideFile: (f: FileItem) => void
  toast: (text: string) => void
}

/** 导出 PANEL_TABS 常量配置。 */
const PANEL_TABS = [
  { id: 'overview' as const, label: '概览' },
  { id: 'debug' as const, label: '调试' },
  { id: 'status' as const, label: '状态' },
  { id: 'files' as const, label: '文件' },
]

const FILE_NAME_TEXT_LIMIT = 20
const FILE_PATH_TEXT_LIMIT = 30
const clipFileText = (value: string, limit = FILE_NAME_TEXT_LIMIT) => (
  value.length > limit ? `${value.slice(0, limit)}...` : value
)

/** 渲染 RightPanel 组件。 */
export function RightPanel(props: Props) {
  const activeTab = useAppStore((s) => s.activeTab)
  const promptTab = useAppStore((s) => s.promptTab)
  const statusSubTab = useAppStore((s) => s.statusSubTab)
  const promptData = useAppStore((s) => s.promptData)
  const config = useAppStore((s) => s.config)
  const showToolCalls = useAppStore((s) => s.showToolCalls)
  const showThinking = useAppStore((s) => s.showThinking)
  const userActive = useAppStore((s) => s.userActive)
  const selectedUser = useAppStore((s) => s.selectedUser)
  const logs = useAppStore((s) => s.logs)
  const tasks = useAppStore((s) => s.tasks)
  const taskPlans = useAppStore((s) => s.taskPlans)
  const files = useAppStore((s) => s.files)
  const [logResults, setLogResults] = useState<Record<string, { result?: string; loading?: boolean }>>({})
  const set = useAppStore.setState
  const get = useAppStore.getState

  useEffect(() => {
    setLogResults({})
  }, [selectedUser])

  const hasCompletedPlans = taskPlans.some((p) => p.status === 'completed' || p.status === 'aborted')
  const fileGroups = [
    { label: '下载文件', files: files.filter((f) => f.dir === 'download') },
    { label: '上传文件', files: files.filter((f) => f.dir === 'file') },
    { label: '知识库（用户）', files: files.filter((f) => f.dir === 'knowledge') },
    { label: '知识库（全局）', files: files.filter((f) => f.dir === 'global-knowledge') },
  ].filter((g) => g.files.length)

  return (
    <aside className="right glass">
      <div className="panel-head">
        <h3>项目状态</h3>
        <div className="tabs">
          {PANEL_TABS.map((t) => (
            <button key={t.id} className={`tab ${activeTab === t.id ? 'active' : ''}`} onClick={() => set({ activeTab: t.id })}>{t.label}</button>
          ))}
        </div>
      </div>
      <div className="panel-body">
        {/* ── 概览 ── */}
        <div className={`pane ${activeTab === 'overview' ? 'active' : ''}`}>
          <div className="prompt-tabs">
            {PROMPT_TABS.map((p) => (
              <button key={p.id} className={`prompt-tab ${promptTab === p.id ? 'active' : ''}`} onClick={() => set({ promptTab: p.id })}>{p.label}</button>
            ))}
          </div>
          <div className="mono">{promptData[promptTab] || '加载中...'}</div>
        </div>

        {/* ── 调试 ── */}
        <div className={`pane ${activeTab === 'debug' ? 'active' : ''}`}>
          <div className="debug-grid">
            <div className="toggle-card">
              <div><b>流式输出开关</b><p style={{ color: 'var(--text-secondary)', fontSize: 11, marginTop: 2 }}>stream</p></div>
              <div className={`switch ${config.stream ? 'on' : ''}`} onClick={() => props.toggleConfigSwitch('stream')} />
            </div>
            <div className="toggle-card">
              <div><b>调用工具显示</b><p style={{ color: 'var(--text-secondary)', fontSize: 11, marginTop: 2 }}>显示/隐藏工具调用卡片</p></div>
              <div className={`switch ${showToolCalls ? 'on' : ''}`} onClick={() => set({ showToolCalls: !showToolCalls })} />
            </div>
            <div className="toggle-card">
              <div><b>思考过程显示</b><p style={{ color: 'var(--text-secondary)', fontSize: 11, marginTop: 2 }}>显示/隐藏 AI 思考过程</p></div>
              <div className={`switch ${showThinking ? 'on' : ''}`} onClick={() => set({ showThinking: !showThinking })} />
            </div>
            <div className="toggle-card">
              <div><b>任务计划</b><p style={{ color: 'var(--text-secondary)', fontSize: 11, marginTop: 2 }}>AI 自动分解复杂任务为步骤计划</p></div>
              <div className={`switch ${config.acceptTask ? 'on' : ''}`} onClick={() => props.toggleConfigSwitch('accept_task')} />
            </div>

            {/* ── 专用模型（高级） ── */}
            <details className="item" style={{ marginTop: 12 }}>
              <summary className="item-top" style={{ cursor: 'pointer' }}><b>专用模型（高级）（需要自己知道服务商和模型的能力）</b></summary>
              <div className="debug-grid" style={{ marginTop: 8 }}>
                <div className="form-row">
                  <label>图像识别模型</label>
                  <input value={config.visionModel || ''} placeholder="与对话模型相同"
                    onChange={(e) => set((s: AppStore) => ({ config: { ...s.config, visionModel: e.target.value } }))}
                    onBlur={() => props.saveConfigField('vision_model', get().config.visionModel)} />
                </div>
                <div className="form-row">
                  <label>语音识别模型</label>
                  <input value={config.audioTranscriptionModel || ''} placeholder="whisper-1"
                    onChange={(e) => set((s: AppStore) => ({ config: { ...s.config, audioTranscriptionModel: e.target.value } }))}
                    onBlur={() => props.saveConfigField('audio_transcription_model', get().config.audioTranscriptionModel)} />
                </div>
                <div className="form-row">
                  <label>图像生成模型</label>
                  <input value={config.imageGenerationModel || ''} placeholder="dall-e-3"
                    onChange={(e) => set((s: AppStore) => ({ config: { ...s.config, imageGenerationModel: e.target.value } }))}
                    onBlur={() => props.saveConfigField('image_generation_model', get().config.imageGenerationModel)} />
                </div>
                <div className="form-row">
                  <label>图像编辑模型</label>
                  <input value={config.imageEditModel || ''} placeholder="stepfun-step-image-edit-2"
                    onChange={(e) => set((s: AppStore) => ({ config: { ...s.config, imageEditModel: e.target.value } }))}
                    onBlur={() => props.saveConfigField('image_edit_model', get().config.imageEditModel)} />
                </div>
                <div className="form-row">
                  <label>语音生成模型</label>
                  <input value={config.speechGenerationModel || ''} placeholder="tts-1"
                    onChange={(e) => set((s: AppStore) => ({ config: { ...s.config, speechGenerationModel: e.target.value } }))}
                    onBlur={() => props.saveConfigField('speech_generation_model', get().config.speechGenerationModel)} />
                </div>
                <div className="form-row">
                  <label>语音生语音模型</label>
                  <input value={config.speechToSpeechModel || ''} placeholder="留空则不启用"
                    onChange={(e) => set((s: AppStore) => ({ config: { ...s.config, speechToSpeechModel: e.target.value } }))}
                    onBlur={() => props.saveConfigField('speech_to_speech_model', get().config.speechToSpeechModel)} />
                </div>
                <div className="form-row">
                  <label>视频生成模型</label>
                  <input value={config.videoGenerationModel || ''} placeholder="留空则不启用"
                    onChange={(e) => set((s: AppStore) => ({ config: { ...s.config, videoGenerationModel: e.target.value } }))}
                    onBlur={() => props.saveConfigField('video_generation_model', get().config.videoGenerationModel)} />
                </div>
              </div>
            </details>

            <div className="item">
              <div className="item-top"><b>用户模型设置</b><span className="pill">{selectedUser || '-'}</span></div>
              <div className="debug-grid" style={{ marginTop: 10 }}>
                <div className="form-row">
                  <label>api 模型</label>
                  <input value={config.model} onChange={(e) => set((s: AppStore) => ({ config: { ...s.config, model: e.target.value } }))} onBlur={() => props.saveConfigField('model', get().config.model)} />
                </div>
                <div className="form-row">
                  <label>base-url</label>
                  <input value={config.baseUrl} onChange={(e) => set((s: AppStore) => ({ config: { ...s.config, baseUrl: e.target.value } }))} onBlur={() => props.saveConfigField('base_url', get().config.baseUrl)} />
                </div>
                <div className="form-row">
                  <label>key</label>
                  <div className="key-shell">
                    <input type="password" placeholder="输入密钥，回车或点保存生效" value={config.keyDraft}
                      onChange={(e) => set((s: AppStore) => ({ config: { ...s.config, keyDraft: e.target.value } }))}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void props.saveConfigField('api_key', get().config.keyDraft); set((s: AppStore) => ({ config: { ...s.config, keyDraft: '' } })); props.toast('密钥已保存') } }}
                      onBlur={() => { const keyDraft = get().config.keyDraft.trim(); if (!keyDraft) return; void props.saveConfigField('api_key', keyDraft); set((s: AppStore) => ({ config: { ...s.config, keyDraft: '' } })); props.toast('密钥已保存') }}
                    />
                  </div>
                  <div className="key-hint">密钥不显示明文，回车或点"保存"生效。请勿在密钥处为空时点击保存，鼠标脱离输入框后会自动保存</div>
                </div>
              </div>
            </div>
            <div className="file-toolbar" style={{ marginTop: 12 }}>
              <button className="btn btn-primary small" onClick={props.saveAllConfig}>保存</button>
              <button className="btn btn-ghost small" onClick={props.applyConfig}>重新加载</button>
              <button className="btn btn-ghost small" onClick={props.restoreConfig}>恢复</button>
            </div>
            <div className="file-toolbar">
              <button className="btn btn-ghost small" style={{ gridColumn: '1/-1' }} onClick={props.reloadAgent}>刷新 重载</button>
            </div>
          </div>
        </div>

        {/* ── 状态 ── */}
        <div className={`pane ${activeTab === 'status' ? 'active' : ''}`}>
          <div className="prompt-tabs" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
            <button className={`prompt-tab ${statusSubTab === 'logs' ? 'active' : ''}`} onClick={() => (set({ statusSubTab: 'logs' }), props.loadToolLogs())}>日志</button>
            <button className={`prompt-tab ${statusSubTab === 'tasks' ? 'active' : ''}`} onClick={() => (set({ statusSubTab: 'tasks' }), props.loadTasks())}>定时任务</button>
            <button className={`prompt-tab ${statusSubTab === 'task-plans' ? 'active' : ''}`} onClick={() => (set({ statusSubTab: 'task-plans' }), props.loadTaskPlans())}>任务计划</button>
          </div>

          {statusSubTab === 'logs' && (
            <div className="list">
              {!logs.length && <div style={{ color: 'var(--text-secondary)', fontSize: 12, padding: 4 }}>{userActive ? '用户暂时没有工具调用日志...' : '选择用户后加载日志...'}</div>}
              {logs.map((log) => {
                const lr = logResults[String(log._key)]
                const handleClick = async () => {
                  if (!log.id || lr) return
                  setLogResults((p) => ({ ...p, [String(log._key)]: { loading: true } }))
                  try {
                    const r = await props.loadToolResult(log.id)
                    setLogResults((p) => ({ ...p, [String(log._key)]: { result: r || '(无输出)' } }))
                  } catch {
                    setLogResults((p) => ({ ...p, [String(log._key)]: { result: '加载失败' } }))
                  }
                }
                return (
                  <div key={log._key} className={`log-row ${log.success ? '' : 'fail'} ${log.id ? 'clickable' : ''}`} onClick={handleClick}>
                    <div>{log.text}</div>
                    {lr?.loading && <div className="log-loading">加载结果中...</div>}
                    {lr?.result && <pre className="log-result">{lr.result}</pre>}
                  </div>
                )
              })}
            </div>
          )}

          {statusSubTab === 'tasks' && (
            <div>
              <div className="file-toolbar"><button className="btn btn-ghost small" onClick={props.loadTasks}>刷新</button></div>
              {!tasks.length && <div style={{ color: 'var(--text-secondary)', fontSize: 12, padding: 4 }}>暂无定时任务</div>}
              {tasks.map((task) => (
                <div key={task.id} className="item">
                  <div className="item-top"><b>[{task.type === 'daily' ? '每日' : '单次'}] {task.time}</b><span className="pill">{task.id}</span></div>
                  <p style={{ color: 'var(--text-primary)', fontSize: 12, marginTop: 4 }}>{task.command}</p>
                  {task.last_run && <p style={{ color: 'var(--text-secondary)', fontSize: 10, marginTop: 2 }}>上次执行: {task.last_run}</p>}
                  <div className="file-actions"><button className="btn btn-danger small" onClick={() => props.deleteTask(task.id)}>删除</button></div>
                </div>
              ))}
            </div>
          )}

          {statusSubTab === 'task-plans' && (
            <div>
              <div className="file-toolbar">
                <button className="btn btn-ghost small" onClick={props.loadTaskPlans}>刷新</button>
                {hasCompletedPlans && <button className="btn btn-danger small" onClick={props.clearCompletedPlans}>全部删除</button>}
              </div>
              {!taskPlans.length && <div style={{ color: 'var(--text-secondary)', fontSize: 12, padding: 4 }}>暂无任务计划</div>}
              {taskPlans.map((plan) => (
                <div key={plan.id} className="item">
                  <div className="item-top"><b>{plan.title}</b><span className="pill" style={{ background: planStatusColor(plan.status) }}>{planStatusLabel(plan.status)}</span></div>
                  <p style={{ color: 'var(--text-primary)', fontSize: 12, marginTop: 4 }}>{plan.description}</p>
                  {plan.steps.map((s) => <div key={s.id} style={{ margin: '3px 0', fontSize: 11, color: 'var(--text-secondary)' }}>{planStepIcon(s.status)} {s.description}</div>)}
                  <div className="file-actions">
                    {plan.status !== 'completed' && plan.status !== 'aborted' && <button className="btn btn-danger small" onClick={() => props.abortPlan(plan.id)}>中止</button>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── 文件 ── */}
        <div className={`pane ${activeTab === 'files' ? 'active' : ''}`}>
          <div className="file-toolbar">
            <button className="btn btn-ghost small" onClick={props.loadFileList}>刷新</button>
            <button className="btn btn-danger small" onClick={props.deleteAllFiles}>全部删除</button>
            <button className="btn btn-ghost small" onClick={props.deleteCheckedFiles}>批量删除</button>
          </div>
          <div className="list">
            {!files.length && <div style={{ color: 'var(--text-secondary)', fontSize: 12, padding: 4 }}>选择用户后加载...</div>}
            {fileGroups.map((group) => (
              <div key={group.label}>
                <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1.2, color: 'var(--text-tertiary)', padding: '6px 0 4px', borderBottom: '1px solid var(--glass-border)', marginBottom: 6 }}>
                  {group.label} ({group.files.length})
                </div>
                {group.files.map((file) => (
                  <div key={file._key} className="item">
                    <div className="file-row">
                      <label className="file-check-label">
                        <input className="file-check" type="checkbox" checked={file.checked} onChange={(e) => set({ files: get().files.map((f) => (f._key === file._key ? { ...f, checked: e.target.checked } : f)) })} />
                      </label>
                      <div className="file-main">
                        <span className="file-name" title={file.name}>{clipFileText(file.name)}</span>
                        <span className="file-path" title={file.path}>{clipFileText(file.path, FILE_PATH_TEXT_LIMIT)}</span>
                      </div>
                      <span className="pill">{file.sizeStr}{file.mtimeStr ? ` · ${file.mtimeStr}` : ''}</span>
                    </div>
                    <div className="file-actions">
                      <button className="btn btn-ghost small" onClick={() => props.guideFile(file)}>引用</button>
                      <button className="btn btn-ghost small" onClick={() => props.downloadFile(file)}>下载</button>
                      <button className="btn btn-danger small" onClick={() => props.deleteFile(file)}>删除</button>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  )
}
