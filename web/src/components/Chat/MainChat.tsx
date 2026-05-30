/** web/src/components/Chat/MainChat.tsx 模块。 */
import { useAppStore } from '@/store/useAppStore'
import type { Conversation, Message } from '@/types'
import type { ChangeEvent, DragEvent, ClipboardEvent, KeyboardEvent } from 'react'
import { TopBar } from './TopBar'
import { MessageList } from './MessageList'
import { Composer } from './Composer'

/** 描述 Props 数据结构。 */
interface Props {
  saveChat: () => Promise<void>
  newChat: () => Promise<void>
  continueAfterMaxRounds: () => void
  sendMessage: () => Promise<void>
  stopRun: () => void
  sendCommand: (cmd: string) => Promise<void>
  continueConversation: () => Promise<void>
  loadConversation: (c: Conversation | { id: '__current__' }) => Promise<void>
  removeAttach: (i: number) => void
  onUploadFiles: (e: ChangeEvent<HTMLInputElement>) => void
  onPaste: (e: ClipboardEvent<HTMLTextAreaElement>) => void
  onTextareaKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void
  onDragEnter: () => void
  onDragLeave: () => void
  onDrop: (e: DragEvent) => void
  onChatScroll: () => void
  patchMessage: (id: number, patch: Partial<Message> | ((m: Message) => Message)) => void
  copyMsg: (m: Message) => void
  loadToolResult: (logId: string) => Promise<string>
  chatRef: React.RefObject<HTMLDivElement>
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

/** 渲染 MainChat 组件。 */
export function MainChat({
  saveChat, newChat, continueAfterMaxRounds, sendMessage, stopRun, sendCommand,
  continueConversation, loadConversation, removeAttach, onUploadFiles, onPaste,
  onTextareaKeyDown, onDragEnter, onDragLeave, onDrop, onChatScroll,
  patchMessage, copyMsg, loadToolResult, chatRef, textRef, uploadRef,
  rejectPlan, approvePlan, modifyPlan, exitAbortPlan, stopModifyPlan, continuePlan, exitPlan,
}: Props) {
  const dragging = useAppStore((s) => s.dragging)

  return (
    <main
      className="main glass"
      id="main-panel"
      onDragEnter={(e) => { e.preventDefault(); onDragEnter() }}
      onDragLeave={(e) => { e.preventDefault(); onDragLeave() }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => { e.preventDefault(); onDrop(e) }}
    >
      {dragging && (
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(255,255,255,0.06)', border: '2px dashed rgba(255,255,255,0.12)', borderRadius: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10, pointerEvents: 'none' }}>
          <span style={{ background: 'rgba(255,255,255,0.06)', padding: '16px 32px', borderRadius: 16, fontSize: 16 }}>📎 释放文件上传</span>
        </div>
      )}

      <TopBar saveChat={saveChat} newChat={newChat} />
      <MessageList patchMessage={patchMessage} copyMsg={copyMsg} continueAfterMaxRounds={continueAfterMaxRounds} chatRef={chatRef} onChatScroll={onChatScroll} loadToolResult={loadToolResult} />
      <Composer
        sendCommand={sendCommand} sendMessage={sendMessage} stopRun={stopRun}
        continueConversation={continueConversation} loadConversation={loadConversation}
        removeAttach={removeAttach} onUploadFiles={onUploadFiles} onPaste={onPaste}
        onTextareaKeyDown={onTextareaKeyDown} textRef={textRef} uploadRef={uploadRef}
        rejectPlan={rejectPlan} approvePlan={approvePlan} modifyPlan={modifyPlan}
        exitAbortPlan={exitAbortPlan} stopModifyPlan={stopModifyPlan} continuePlan={continuePlan} exitPlan={exitPlan}
      />
    </main>
  )
}
