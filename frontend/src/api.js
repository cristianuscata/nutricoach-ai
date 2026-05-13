/**
 * api.js — Cliente HTTP/SSE para el backend NutriCoach.
 *
 * Todos los fetch apuntan a VITE_API_BASE (configurable por .env).
 * En dev local, Vite proxy puede reescribir /api → localhost:8000.
 */

const BASE = import.meta.env.VITE_API_BASE || '/api'

// -------------------------------------------------------------------------- //
// Clientes                                                                    //
// -------------------------------------------------------------------------- //

export async function fetchClients() {
  const res = await fetch(`${BASE}/clients`)
  if (!res.ok) throw new Error(`fetchClients: ${res.status}`)
  const data = await res.json()
  return data.clients ?? []
}

// -------------------------------------------------------------------------- //
// Conversaciones                                                              //
// -------------------------------------------------------------------------- //

export async function fetchConversations(clientId) {
  const res = await fetch(`${BASE}/agent/conversations?client_id=${clientId}`)
  if (!res.ok) throw new Error(`fetchConversations: ${res.status}`)
  const data = await res.json()
  return data.conversations ?? []
}

export async function fetchConversation(conversationId) {
  const res = await fetch(`${BASE}/agent/conversations/${conversationId}`)
  if (!res.ok) throw new Error(`fetchConversation: ${res.status}`)
  return res.json()
}

// -------------------------------------------------------------------------- //
// Streaming del agente (SSE)                                                  //
// -------------------------------------------------------------------------- //

/**
 * Abre un SSE stream hacia /agent/stream y llama a los callbacks por evento.
 *
 * @param {object} params
 * @param {string} params.clientId
 * @param {string} params.message
 * @param {string|null} params.conversationId
 * @param {function} params.onMeta       - ({ conversation_id, model_used, routing_reason })
 * @param {function} params.onToken      - (content: string)
 * @param {function} params.onToolCall   - ({ tool, input })
 * @param {function} params.onDone       - ({ conversation_id })
 * @param {function} params.onError      - (detail: string)
 * @returns {EventSource} — llamar .close() para cancelar
 */
export function streamAgent({ clientId, message, conversationId, onMeta, onToken, onToolCall, onDone, onError }) {
  const params = new URLSearchParams({
    client_id: clientId,
    message,
    ...(conversationId ? { conversation_id: conversationId } : {}),
  })

  const url = `${BASE}/agent/stream?${params}`
  const es = new EventSource(url)

  es.addEventListener('meta', (e) => {
    try { onMeta?.(JSON.parse(e.data)) } catch (_) {}
  })

  es.addEventListener('token', (e) => {
    try { onToken?.(JSON.parse(e.data).content) } catch (_) {}
  })

  es.addEventListener('tool_call', (e) => {
    try { onToolCall?.(JSON.parse(e.data)) } catch (_) {}
  })

  es.addEventListener('done', (e) => {
    try { onDone?.(JSON.parse(e.data)) } catch (_) {}
    es.close()
  })

  es.addEventListener('error', (e) => {
    try {
      const parsed = JSON.parse(e.data)
      onError?.(parsed.detail ?? 'Error desconocido')
    } catch (_) {
      onError?.('Conexión interrumpida')
    }
    es.close()
  })

  // ping events — ignorar
  es.addEventListener('ping', () => {})

  return es
}
