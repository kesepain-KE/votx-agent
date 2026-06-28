/** 描述 Props 数据结构。 */
import { useAppStore } from '@/store/useAppStore'
import type { KeyboardEvent, ChangeEvent, ClipboardEvent } from 'react'
import { COMMANDS, planStepIcon } from '@/hooks/useAppActions'
import { ContextUsageBar } from './ContextUsageBar'

/** 描述 Props 数据结构。 */
interface Props {
  sendCommand: (cmd: string) => Promise<void>
  sendMessage: () => Promise<void>
  stopRun: () => void
  continueConversation: () => Promise<void>
  loadConversation: (c: { id: '__current__' }) => Promise<void>
  removeAttach: (i: number) => void
  onUploadFiles: (e: ChangeEvent<HTMLInputElement>) => void
  onPaste: (e: ClipboardEvent<HTMLTextAreaElement>) => void
  onTextareaKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void
  textRef: React.RefObject<HTMLTextAreaElement>
  uploadRef: React.RefObject<HTMLInputElement>
  rejectPlan: () => Promise<void>
  approvePlan: () => Promise<void>
  modifyPlan: () => void
  exitAbortPlan: () => Promise<void>
  stopModifyPlan: () => Promise<void>
  continuePlan: () => Promise<void>
  exitPlan: () => void
}

/** 渲染 Composer 组件。 */
export function Composer({ sendCommand, sendMessage, stopRun, continueConversation, loadConversation, removeAttach, onUploadFiles, onPaste, onTextareaKeyDown, textRef, uploadRef, rejectPlan, approvePlan, modifyPlan, exitAbortPlan, stopModifyPlan, continuePlan, exitPlan }: Props) {
  const input = useAppStore((s) => s.input)
  const set = useAppStore.setState
  const userActive = useAppStore((s) => s.userActive)
  const running = useAppStore((s) => s.running)
  const isPreview = useAppStore((s) => s.isPreview)
  const attachChips = useAppStore((s) => s.attachChips)
  const activePlan = useAppStore((s) => s.activePlan)
  const planPhase = useAppStore((s) => s.planPhase)
  const planDoneCount = useAppStore((s) => s.activePlan?.steps.filter((step) => step.status === 'completed').length || 0)

  return (
    <footer className="composer">
      <div className="quick">
        {COMMANDS.map((cmd) => (
          <button className="chip" key={cmd} onClick={() => sendCommand(cmd)}>{cmd}</button>
        ))}
        <ContextUsageBar />
      </div>

      {isPreview && (
        <div className="preview-banner">
          <span>📋 归档预览 — 只读模式</span>
          <button className="btn btn-ghost small" onClick={continueConversation}>从此对话继续</button>
          <button className="btn btn-ghost small" onClick={() => loadConversation({ id: '__current__' })}>返回当前对话</button>
        </div>
      )}

      {!!attachChips.length && (
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginBottom: 10 }}>
          {attachChips.map((file, i) => (
            <span className="attach-chip" key={`${file.name}-${i}`}>
              📎 {file.name}
              <span className="remove-file" onClick={() => removeAttach(i)}>×</span>
            </span>
          ))}
        </div>
      )}

      {activePlan && (
        <div className={`plan-bubble ${planPhase === 'review' ? 'reviewing' : ''} ${planPhase === 'executing' ? 'executing' : ''} ${planPhase === 'completed' ? 'completed' : ''}`}>
          <div className="plan-bubble-header">
            <span className="plan-bubble-icon">{planPhase === 'completed' ? '✓' : '📋'}</span>
            <span className="plan-bubble-title">{activePlan.title}</span>
            {planPhase === 'executing' && <span className="plan-bubble-progress">{planDoneCount}/{activePlan.steps.length} 步</span>}
            {planPhase === 'completed' && <span className="plan-bubble-badge">已完成</span>}
            {planPhase === 'paused' && <span className="plan-bubble-badge" style={{ background: '#ff9800' }}>已暂停</span>}
          </div>
          {activePlan.description && <p className="plan-bubble-desc">{activePlan.description}</p>}
          <div className="plan-bubble-steps">
            {activePlan.steps.map((s) => (
              <div key={s.id} className={`plan-step-row step-${s.status || 'pending'}`}>
                <span className="plan-step-icon">{planStepIcon(s.status)}</span>
                <span className="plan-step-desc">{s.description}</span>
                {s.result && <span className="plan-step-result" title={s.result}>{s.result.length > 40 ? `${s.result.slice(0, 40)}...` : s.result}</span>}
                {s.error && <span className="plan-step-error">⚠ {s.error.length > 30 ? `${s.error.slice(0, 30)}...` : s.error}</span>}
              </div>
            ))}
          </div>
          <div className="plan-bubble-actions">
            {planPhase === 'review' && (
              <>
                <button className="btn btn-danger small" onClick={rejectPlan}>拒绝</button>
                <button className="btn btn-ghost small" onClick={modifyPlan}>修改</button>
                <button className="btn btn-primary small" onClick={approvePlan}>批准</button>
              </>
            )}
            {planPhase === 'executing' && (
              <>
                <button className="btn btn-danger small" onClick={exitAbortPlan}>退出并终止</button>
                <button className="btn btn-ghost small" onClick={stopModifyPlan}>停止并修改</button>
              </>
            )}
            {planPhase === 'paused' && (
              <>
                <button className="btn btn-danger small" onClick={exitAbortPlan}>退出并终止</button>
                <button className="btn btn-primary small" onClick={continuePlan}>继续执行</button>
                <button className="btn btn-ghost small" onClick={modifyPlan}>修改</button>
              </>
            )}
            {planPhase === 'completed' && <button className="btn btn-primary small" onClick={exitPlan}>退出任务</button>}
          </div>
        </div>
      )}

      <div className="input-row">
        <input type="file" ref={uploadRef} multiple onChange={onUploadFiles} accept="*/*" style={{ display: 'none' }} />
        <button className="upload-btn" onClick={() => uploadRef.current?.click()} title="上传文件" disabled={isPreview}>＋</button>
        <textarea
          ref={textRef}
          value={input}
          disabled={!userActive || running || isPreview}
          placeholder={isPreview ? '归档预览模式（只读），请点击"从此对话继续"后再聊天' : '输入消息或 / 命令... (Enter 发送，Shift+Enter 换行)'}
          rows={1}
          onChange={(e) => set({ input: e.target.value })}
          onKeyDown={onTextareaKeyDown}
          onPaste={onPaste}
          style={{ resize: 'none', overflowY: 'auto', minHeight: 22, maxHeight: 150, lineHeight: 1.5, width: '100%' }}
        />
        {running ? (
          <button className="send-btn stop" onClick={stopRun}>停止</button>
        ) : (
          <button className="send-btn" disabled={!userActive || isPreview} onClick={sendMessage}>发送</button>
        )}
      </div>
    </footer>
  )
}
