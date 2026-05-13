import { useState, useEffect, useRef, useCallback } from 'react'
import {
  fetchClients,
  fetchConversations,
  fetchConversation,
  streamAgent,
} from './api.js'

/* ================================================================
   Utilidades
   ================================================================ */

function initials(name = '') {
  return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()
}

function goalLabel(g) {
  const MAP = {
    weight_loss: '⚖️ Bajar peso',
    maintain_muscle_mass: '💪 Mantener músculo',
    athletic_performance: '🏃 Performance',
    healthy_pregnancy: '🤰 Embarazo saludable',
    address_anemia: '🩸 Anemia',
    improve_energy: '⚡ Energía',
  }
  return MAP[g] || g
}

/* ================================================================
   Componente: ProfileChips
   ================================================================ */
function ProfileChips({ client }) {
  if (!client) return null
  const goals   = (client.goals || []).slice(0, 3)
  const allerg  = (client.allergies || []).slice(0, 2)
  const diets   = (client.dietary_restrictions || []).slice(0, 2)

  return (
    <div className="profile-chips">
      {goals.map(g  => <span key={g}  className="chip goal">{goalLabel(g)}</span>)}
      {allerg.map(a => <span key={a}  className="chip allergy">⚠️ {a}</span>)}
      {diets.map(d  => <span key={d}  className="chip diet">🥗 {d}</span>)}
    </div>
  )
}

/* ================================================================
   Componente: Message
   ================================================================ */
function Message({ msg, streaming }) {
  return (
    <div className={`message ${msg.role}`}>
      <div className="msg-avatar">
        {msg.role === 'human' ? '👤' : '🥗'}
      </div>
      <div className="msg-body">
        {msg.toolCall && (
          <div className="tool-indicator">
            <span>⚡</span>
            Consultando {msg.toolCall === 'get_nutrition_facts'
              ? 'USDA FoodData Central'
              : 'búsqueda web'}…
          </div>
        )}
        <div className="msg-bubble">
          {msg.content}
          {streaming && <span className="cursor" />}
        </div>
        {msg.routing && (
          <div className="routing-badge">
            {msg.routing.model} · {msg.routing.reason}
          </div>
        )}
      </div>
    </div>
  )
}

/* ================================================================
   Componente: Sidebar
   ================================================================ */
function Sidebar({ clients, activeClient, onSelectClient, conversations, activeConvId, onSelectConv, onNewConv, loadingClients }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <span>🥗</span> NutriCoach
        </div>
        <p className="sidebar-subtitle">Asistente nutricional con IA</p>
      </div>

      <p className="sidebar-section-title">Clientes</p>

      <div className="client-list">
        {loadingClients ? (
          <div style={{ padding: '16px', color: 'var(--text-muted)', fontSize: '12px' }}>
            Cargando…
          </div>
        ) : clients.map(c => (
          <div key={c.client_id}>
            <div
              className={`client-item ${activeClient?.client_id === c.client_id ? 'active' : ''}`}
              onClick={() => onSelectClient(c)}
            >
              <div className="client-avatar">{initials(c.name)}</div>
              <div>
                <div className="client-name">{c.name}</div>
                <div className="client-meta">
                  {c.age}a · {c.sex === 'F' ? '♀' : '♂'} · {c.weight_kg}kg
                </div>
              </div>
            </div>

            {/* Conversaciones del cliente activo */}
            {activeClient?.client_id === c.client_id && (
              <div className="conv-list">
                {conversations.map(conv => (
                  <div
                    key={conv.conversation_id}
                    className={`conv-item ${activeConvId === conv.conversation_id ? 'active' : ''}`}
                    onClick={() => onSelectConv(conv.conversation_id)}
                  >
                    <span className="conv-item-icon">💬</span>
                    {conv.message_count} msg · {conv.updated_at
                      ? new Date(conv.updated_at).toLocaleDateString('es-PE', { month: 'short', day: 'numeric' })
                      : '—'}
                  </div>
                ))}
                <button className="new-conv-btn" onClick={onNewConv}>
                  ＋ Nueva conversación
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </aside>
  )
}

/* ================================================================
   Componente principal: App
   ================================================================ */
export default function App() {
  const [clients, setClients]           = useState([])
  const [loadingClients, setLoadingCl]  = useState(true)
  const [activeClient, setActiveClient] = useState(null)
  const [conversations, setConvs]       = useState([])
  const [activeConvId, setActiveConvId] = useState(null)
  const [messages, setMessages]         = useState([])
  const [input, setInput]               = useState('')
  const [streaming, setStreaming]        = useState(false)
  const [pendingTool, setPendingTool]   = useState(null)

  const chatEndRef  = useRef(null)
  const textareaRef = useRef(null)
  const esRef       = useRef(null)

  /* ---- Load clients ---- */
  useEffect(() => {
    fetchClients()
      .then(setClients)
      .catch(console.error)
      .finally(() => setLoadingCl(false))
  }, [])

  /* ---- Scroll to bottom ---- */
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  /* ---- Select client ---- */
  const handleSelectClient = useCallback(async (client) => {
    setActiveClient(client)
    setMessages([])
    setActiveConvId(null)
    setPendingTool(null)
    try {
      const convs = await fetchConversations(client.client_id)
      setConvs(convs)
      // Auto-abrir la más reciente
      if (convs.length > 0) {
        handleSelectConv(convs[0].conversation_id)
      }
    } catch (e) { console.error(e) }
  }, [])

  /* ---- Select conversation ---- */
  const handleSelectConv = useCallback(async (convId) => {
    setActiveConvId(convId)
    setPendingTool(null)
    try {
      const conv = await fetchConversation(convId)
      const msgs = (conv.messages || [])
        .filter(m => m.role !== 'system')
        .map((m, i) => ({ id: i, role: m.role === 'ai' ? 'ai' : 'human', content: m.content }))
      setMessages(msgs)
    } catch (e) { console.error(e) }
  }, [])

  /* ---- New conversation ---- */
  const handleNewConv = useCallback(() => {
    setActiveConvId(null)
    setMessages([])
    setPendingTool(null)
  }, [])

  /* ---- Send message ---- */
  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || !activeClient || streaming) return

    // Cerrar stream anterior si lo hubiera
    esRef.current?.close()

    setInput('')
    setPendingTool(null)

    // Agregar mensaje humano
    const humanMsg = { id: Date.now(), role: 'human', content: text }
    setMessages(prev => [...prev, humanMsg])

    // Placeholder del AI mientras streamea
    const aiMsgId = Date.now() + 1
    let routingInfo = null

    setMessages(prev => [...prev, { id: aiMsgId, role: 'ai', content: '', streaming: true }])
    setStreaming(true)

    esRef.current = streamAgent({
      clientId: activeClient.client_id,
      message: text,
      conversationId: activeConvId,

      onMeta: (meta) => {
        routingInfo = { model: meta.model_used, reason: meta.routing_reason }
        if (meta.conversation_id && !activeConvId) {
          setActiveConvId(meta.conversation_id)
        }
      },

      onToken: (token) => {
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId ? { ...m, content: m.content + token } : m
        ))
      },

      onToolCall: ({ tool }) => {
        setPendingTool(tool)
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId ? { ...m, toolCall: tool } : m
        ))
      },

      onDone: async ({ conversation_id }) => {
        setPendingTool(null)
        setStreaming(false)
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId
            ? { ...m, streaming: false, toolCall: null, routing: routingInfo }
            : m
        ))
        // Refrescar lista de conversaciones
        if (activeClient) {
          const convs = await fetchConversations(activeClient.client_id)
          setConvs(convs)
          setActiveConvId(conversation_id)
        }
      },

      onError: (detail) => {
        setPendingTool(null)
        setStreaming(false)
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId
            ? { ...m, streaming: false, content: `⚠️ Error: ${detail}` }
            : m
        ))
      },
    })
  }, [input, activeClient, activeConvId, streaming])

  /* ---- Keyboard handler ---- */
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  /* ---- Auto-resize textarea ---- */
  const handleInputChange = (e) => {
    setInput(e.target.value)
    const ta = textareaRef.current
    if (ta) { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px' }
  }

  /* ================================================================
     Render
     ================================================================ */
  return (
    <div className="app">

      {/* ---- Sidebar ---- */}
      <Sidebar
        clients={clients}
        loadingClients={loadingClients}
        activeClient={activeClient}
        onSelectClient={handleSelectClient}
        conversations={conversations}
        activeConvId={activeConvId}
        onSelectConv={handleSelectConv}
        onNewConv={handleNewConv}
      />

      {/* ---- Main ---- */}
      <main className="main">

        {/* Topbar */}
        {activeClient ? (
          <div className="topbar">
            <div>
              <div className="topbar-title">{activeClient.name}</div>
            </div>
            <ProfileChips client={activeClient} />
          </div>
        ) : (
          <div className="topbar">
            <div className="topbar-title" style={{ color: 'var(--text-muted)' }}>
              Selecciona un cliente →
            </div>
          </div>
        )}

        {/* Chat */}
        {!activeClient ? (
          <div className="no-client">
            <div className="no-client-icon">🥗</div>
            <h2>Bienvenido a NutriCoach</h2>
            <p>Selecciona un cliente en el panel lateral para comenzar.</p>
          </div>
        ) : (
          <>
            <div className="chat-area">
              {messages.length === 0 && !streaming ? (
                <div className="empty-state">
                  <div className="empty-state-icon">💬</div>
                  <h2>Nueva conversación</h2>
                  <p>
                    Escribe un mensaje para comenzar. El agente usa el perfil
                    completo de {activeClient.name} y puede consultar USDA en tiempo real.
                  </p>
                </div>
              ) : (
                messages.map(msg => (
                  <Message key={msg.id} msg={msg} streaming={msg.streaming} />
                ))
              )}

              {/* Indicador de carga inicial */}
              {streaming && messages.at(-1)?.content === '' && (
                <div className="message ai">
                  <div className="msg-avatar">🥗</div>
                  <div className="msg-body">
                    <div className="msg-bubble">
                      <div className="loading-dots">
                        <span /><span /><span />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* Composer */}
            <div className="composer">
              <div className="composer-inner">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  placeholder={`Escríbele a NutriCoach sobre ${activeClient.name.split(' ')[0]}…`}
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  disabled={streaming}
                />
                <button
                  className="send-btn"
                  onClick={handleSend}
                  disabled={!input.trim() || streaming}
                  title="Enviar (Enter)"
                >
                  ➤
                </button>
              </div>
              <p className="composer-hint">
                Enter para enviar · Shift+Enter para nueva línea
                {streaming && ' · Recibiendo respuesta…'}
              </p>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
