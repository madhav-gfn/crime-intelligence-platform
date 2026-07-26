import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Send, Terminal, AlertCircle } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import { chatApi } from '../api/chat';
import type { TurnOut, ChatResponse } from '../types/api';

export default function ChatPage() {
  const [messages, setMessages] = useState<TurnOut[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(localStorage.getItem('crimint_chat_session'));
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: caps } = useQuery({ queryKey: ['chatCaps'], queryFn: chatApi.capabilities });

  // Generate session ID if not exists
  useEffect(() => {
    if (!sessionId) {
      const id = 'sess_' + Math.random().toString(36).substr(2, 9);
      setSessionId(id);
      localStorage.setItem('crimint_chat_session', id);
    }
  }, [sessionId]);

  // Load history if exists
  useQuery({
    queryKey: ['chatHistory', sessionId],
    queryFn: () => chatApi.sessionHistory(sessionId!),
    enabled: !!sessionId,
    retry: false, // 404 is fine for new sessions
  });

  const chatMutation = useMutation({
    mutationFn: (msg: string) => chatApi.sendMessage({ message: msg, session_id: sessionId }),
    onSuccess: (data: ChatResponse, variables: string) => {
      setMessages(prev => [
        ...prev,
        { role: 'user', text: variables, timestamp: new Date().toISOString() },
        { role: 'assistant', text: data.reply, intent: data.intent, timestamp: new Date().toISOString(), _data: data } as any
      ]);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    }
  });

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || chatMutation.isPending) return;
    
    // Optimistic UI update for user message
    setMessages(prev => [...prev, { role: 'user', text: input, timestamp: new Date().toISOString() }]);
    chatMutation.mutate(input);
    setInput('');
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  };

  const exampleQueries = [
    "Who is ACC-002543?",
    "Forecast for Mysore",
    "Show hotspots",
    "Who is connected to ACC-002543?"
  ];

  return (
    <div className="page-body flex flex-col h-screen" style={{ maxHeight: '100vh', paddingBottom: '20px' }}>
      <PageHeader 
        title="Conversational Interface" 
        eyebrow="Pillar 1"
        description="Rule-based natural language routing to analytics microservices."
      />

      <div className="chat-layout flex-1 overflow-hidden">
        {/* Left Sidebar: Capabilities */}
        <div className="card h-full flex flex-col overflow-hidden hidden md:flex">
          <div className="flex items-center gap-2 text-cyan font-bold mb-4">
            <Terminal size={18} /> Supported Intents
          </div>
          <div className="text-xs text-muted mb-4 pb-4 border-b border-[var(--border)]">
            {caps?.description}
          </div>
          <div className="overflow-y-auto flex-1 pr-2">
            {caps && Object.entries(caps.supported_intents).map(([intent, desc]) => (
              <div key={intent} className="mb-4">
                <div className="text-xs font-mono text-primary bg-[var(--bg-elevated)] p-1 rounded inline-block mb-1 border border-[var(--border)]">
                  {intent}
                </div>
                <div className="text-xs text-muted leading-relaxed">
                  {desc}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Area: Chat Interface */}
        <div className="chat-panel h-full flex flex-col relative">
          <div className="chat-messages">
            {messages.length === 0 && !chatMutation.isPending && (
              <div className="h-full flex flex-col items-center justify-center text-muted gap-4">
                <MessageSquare className="text-dim" size={48} />
                <p>Start a session. Try asking:</p>
                <div className="flex flex-wrap gap-2 justify-center max-w-md">
                  {exampleQueries.map(q => (
                    <button key={q} onClick={() => setInput(q)} className="px-3 py-1 bg-[var(--bg-elevated)] border border-[var(--border)] rounded-full text-xs hover:border-cyan hover:text-cyan transition-colors">
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                {m.role === 'assistant' && m.intent && (
                  <div className="flex items-center gap-2 mb-1 pl-1">
                    <span className="intent-badge">{m.intent}</span>
                    {/* @ts-ignore */}
                    {m._data?.downstream_service && (
                      <span className="text-[10px] font-mono text-muted uppercase">
                        {/* @ts-ignore */}
                        via {m._data.downstream_service} 
                        {/* @ts-ignore */}
                        {m._data.downstream_status ? ` (${m._data.downstream_status})` : ''}
                      </span>
                    )}
                  </div>
                )}
                
                <div className={`chat-bubble ${m.role}`}>
                  {m.text}
                </div>
              </div>
            ))}

            {chatMutation.isPending && (
              <div className="flex flex-col items-start">
                <div className="chat-bubble assistant">
                  <div className="typing-indicator">
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                  </div>
                </div>
              </div>
            )}
            
            {chatMutation.isError && (
              <div className="flex items-center gap-2 text-risk-high text-xs bg-[var(--risk-high-dim)] p-2 rounded border border-[rgba(239,68,68,0.3)] w-fit">
                <AlertCircle size={14} /> Failed to send message. Is the service running?
              </div>
            )}
            
            <div ref={bottomRef} />
          </div>

          <form className="chat-input-row bg-[var(--bg-surface)]" onSubmit={handleSend}>
            <input 
              type="text" 
              className="input chat-input" 
              placeholder="Ask a question..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={chatMutation.isPending}
            />
            <button type="submit" className="btn btn-primary" disabled={!input.trim() || chatMutation.isPending}>
              <Send size={18} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

// Just needed for the empty state icon
import { MessageSquare } from 'lucide-react';
