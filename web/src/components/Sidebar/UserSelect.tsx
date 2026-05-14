import { useAppStore } from '@/store/useAppStore'

interface Props {
  selectUser: () => Promise<void>
}

export function UserSelect({ selectUser }: Props) {
  const users = useAppStore((s) => s.users)
  const selectedUser = useAppStore((s) => s.selectedUser)
  const selectErr = useAppStore((s) => s.selectErr)
  const set = useAppStore.setState

  return (
    <div className="card">
      <div className="section-title">用户选择</div>
      <select value={selectedUser} onChange={(e) => set({ selectedUser: e.target.value })}>
        {users.map((u) => (
          <option key={u} value={u}>{u}</option>
        ))}
      </select>
      <button className="btn btn-primary" onClick={selectUser}>进入</button>
      <div style={{ color: 'var(--danger)', fontSize: 11, marginTop: 6 }}>{selectErr}</div>
    </div>
  )
}
