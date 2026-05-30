/** web/src/App.tsx 模块。 */
import { useAppActions } from '@/hooks/useAppActions'
import { Sidebar } from '@/components/Sidebar/Sidebar'
import { MainChat } from '@/components/Chat/MainChat'
import { RightPanel } from '@/components/RightPanel/RightPanel'
import { Toast } from '@/components/Shared/Toast'
import { ContextMenu } from '@/components/Shared/ContextMenu'
import { ErrorBoundary } from '@/components/Shared/ErrorBoundary'

/** 渲染 App 组件。 */
export default function App() {
  const a = useAppActions()

  return (
    <>
      <div className="app">
        <Sidebar
          profileInitial={a.profileInitial}
          selectUser={a.selectUser}
          loadConversation={a.loadConversation}
          renameConv={a.renameConv}
          deleteConversation={a.deleteConversation}
          openConvMenu={a.openConvMenu}
          loadFromManager={a.loadConversation}
          refreshConversations={a.refreshConversations}
          deleteAllConvs={a.deleteAllConvs}
          refreshOverview={a.refreshOverview}
          toggleThemeMenu={a.toggleThemeMenu}
          chooseTheme={a.chooseTheme}
        />

        <ErrorBoundary>
            <MainChat
              saveChat={a.saveChat}
              newChat={a.newChat}
              continueAfterMaxRounds={a.continueAfterMaxRounds}
              sendMessage={a.sendMessage}
              stopRun={a.stopRun}
              sendCommand={a.sendCommand}
              continueConversation={a.continueConversation}
              loadConversation={a.loadConversation}
              removeAttach={a.removeAttach}
              onUploadFiles={a.onUploadFiles}
              onPaste={a.onPaste}
              onTextareaKeyDown={a.onTextareaKeyDown}
              onDragEnter={a.onDragEnter}
              onDragLeave={a.onDragLeave}
              onDrop={a.onDrop}
              onChatScroll={a.onChatScroll}
              patchMessage={a.patchMessage}
              copyMsg={a.copyMsg}
              chatRef={a.chatRef}
              textRef={a.textRef}
              uploadRef={a.uploadRef}
              rejectPlan={a.rejectPlan}
              approvePlan={a.approvePlan}
              modifyPlan={a.modifyPlan}
              exitAbortPlan={a.exitAbortPlan}
              stopModifyPlan={a.stopModifyPlan}
              exitPlan={a.exitPlan}
            />
        </ErrorBoundary>

        <ErrorBoundary>
          <RightPanel
            toggleConfigSwitch={a.toggleConfigSwitch}
            saveConfigField={a.saveConfigField}
            saveAllConfig={a.saveAllConfig}
            applyConfig={a.applyConfig}
            restoreConfig={a.restoreConfig}
            reloadAgent={a.reloadAgent}
            loadToolLogs={a.loadToolLogs}
            loadTasks={a.loadTasks}
            deleteTask={a.deleteTask}
            loadTaskPlans={a.loadTaskPlans}
            clearCompletedPlans={a.clearCompletedPlans}
            abortPlan={a.abortPlan}
            loadFileList={a.loadFileList}
            deleteAllFiles={a.deleteAllFiles}
            deleteCheckedFiles={a.deleteCheckedFiles}
            downloadFile={a.downloadFile}
            deleteFile={a.deleteFile}
            guideFile={a.guideFile}
            toast={a.toast}
          />
        </ErrorBoundary>
      </div>

      <ContextMenu renameConvFromMenu={a.renameConvFromMenu} deleteConvFromMenu={a.deleteConvFromMenu} />
      <Toast />
    </>
  )
}
