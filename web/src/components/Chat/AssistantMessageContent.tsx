import { ArtifactContent } from './artifacts'

interface Props {
  content: string
  streaming?: boolean
}

export function AssistantMessageContent({ content, streaming = false }: Props) {
  return <ArtifactContent content={content} streaming={streaming} density="normal" />
}
