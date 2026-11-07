import type { SimpleCommand } from './types/ws-client'
import type { ServerMessage, TtsChunkMessage } from './types/ws-server'

export type SocketEvent =
  | { kind: 'open' }
  | { kind: 'closed'; code: number }
  | { kind: 'message'; message: ServerMessage }
  | { kind: 'audio'; chunk: TtsChunkMessage; pcm: Int16Array }

/**
 * The live-session WebSocket: JSON commands and events, plus binary audio in both directions.
 *
 * Every `tts.chunk` message is followed by one binary frame with its audio; the two are delivered
 * together as an `audio` event. The highest `seq` seen is kept for replay after a reconnection.
 */
export class SessionSocket {
  lastSeq = 0
  private socket: WebSocket | null = null
  private pendingChunk: TtsChunkMessage | null = null

  constructor(
    private readonly sessionId: string,
    private readonly onEvent: (event: SocketEvent) => void,
  ) {}

  connect(): void {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${scheme}://${location.host}/ws/sessions/${this.sessionId}`)
    socket.binaryType = 'arraybuffer'
    socket.onopen = () => {
      this.sendJson({ type: 'session.join', last_seq: this.lastSeq })
      this.onEvent({ kind: 'open' })
    }
    socket.onclose = (event) => {
      this.onEvent({ kind: 'closed', code: event.code })
    }
    socket.onmessage = (event: MessageEvent<ArrayBuffer | string>) => {
      this.receive(event.data)
    }
    this.socket = socket
  }

  command(type: SimpleCommand['type']): void {
    this.sendJson({ type })
  }

  endAnswer(): void {
    this.sendJson({ type: 'turn.end' })
  }

  sendAudio(pcm: Int16Array): void {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(pcm)
  }

  close(): void {
    this.socket?.close()
    this.socket = null
  }

  private sendJson(message: Record<string, unknown>): void {
    if (this.socket?.readyState !== WebSocket.OPEN) return
    this.socket.send(JSON.stringify({ ...message, client_msg_id: crypto.randomUUID() }))
  }

  private receive(data: ArrayBuffer | string): void {
    if (typeof data !== 'string') {
      const chunk = this.pendingChunk
      this.pendingChunk = null
      if (chunk) this.onEvent({ kind: 'audio', chunk, pcm: new Int16Array(data) })
      return
    }
    const message = JSON.parse(data) as ServerMessage
    if (message.seq !== null) this.lastSeq = Math.max(this.lastSeq, message.seq)
    if (message.type === 'tts.chunk') {
      this.pendingChunk = message
      return
    }
    this.onEvent({ kind: 'message', message })
  }
}
