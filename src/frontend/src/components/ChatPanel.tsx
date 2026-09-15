import React, { useState, useRef, useEffect } from 'react';
import {
  X,
  Send,
  Wrench,
  Sparkles,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  Bot,
  User,
  HelpCircle,
} from 'lucide-react';
import { ChatMessage } from '../types';
import { sendChatMessage } from '../api/client';

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const SAMPLE_PROMPTS = [
  'Which sites had 3+ major deviations this month?',
  'What are the highest risk sites and why?',
  'Show me deviations at SITE-101',
  'Fetch the CAPA report for SITE-101',
];

export const ChatPanel: React.FC<ChatPanelProps> = ({ isOpen, onClose }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      sender: 'assistant',
      text: 'Hello! I am your ClinGuard compliance assistant. Ask me questions about site risks, protocol deviations, or CAPA reports. All answers are grounded strictly in live database queries via deterministic MCP tools — never guessed.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [expandedPayloadId, setExpandedPayloadId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || input;
    if (!textToSend.trim() || loading) return;

    const userMsgId = Date.now().toString();
    const userMsg: ChatMessage = {
      id: userMsgId,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await sendChatMessage(textToSend);
      const assistantMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: response.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        tool_called: response.tool_called,
        tool_arguments: response.tool_arguments,
        tool_result: response.tool_result,
        grounded: response.grounded,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: `Error contacting compliance backend: ${err.message || 'Unknown error'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const togglePayload = (id: string) => {
    setExpandedPayloadId(expandedPayloadId === id ? null : id);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full sm:w-[480px] bg-white shadow-2xl border-l border-slate-200 flex flex-col animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="p-4 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-teal-500/20 border border-teal-500/40 flex items-center justify-center text-teal-400">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-white m-0 flex items-center space-x-1.5">
              <span>ClinGuard MCP Chat</span>
              <span className="flex items-center text-[10px] font-semibold bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-800/40">
                <ShieldCheck className="w-3 h-3 mr-1" />
                Grounded
              </span>
            </h3>
            <p className="text-[11px] text-slate-400 m-0">Zero-hallucination compliance tool caller</p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Suggested prompts chips */}
      <div className="bg-slate-50 border-b border-slate-200 p-2.5 overflow-x-auto flex space-x-2 scrollbar-none">
        {SAMPLE_PROMPTS.map((prompt, i) => (
          <button
            key={i}
            onClick={() => handleSend(prompt)}
            disabled={loading}
            className="whitespace-nowrap px-2.5 py-1 rounded-full text-[11px] font-medium bg-white border border-slate-200 text-slate-700 hover:bg-teal-50 hover:text-teal-700 hover:border-teal-300 transition shadow-2xs"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Messages stream */}
      <div className="flex-1 p-4 overflow-y-auto space-y-4 text-xs">
        {messages.map((msg) => {
          const isUser = msg.sender === 'user';
          const isPayloadOpen = expandedPayloadId === msg.id;

          return (
            <div
              key={msg.id}
              className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[90%] rounded-2xl p-3.5 shadow-xs ${
                  isUser
                    ? 'bg-teal-600 text-white rounded-br-none'
                    : 'bg-slate-100 text-slate-800 border border-slate-200 rounded-bl-none'
                }`}
              >
                {/* Sender badge & timestamp */}
                <div className="flex items-center justify-between space-x-2 mb-1.5 opacity-75 text-[10px]">
                  <span className="font-bold flex items-center space-x-1">
                    {isUser ? <User className="w-3 h-3 mr-1" /> : <Bot className="w-3 h-3 mr-1 text-teal-600" />}
                    <span>{isUser ? 'You' : 'Compliance Assistant'}</span>
                  </span>
                  <span>{msg.timestamp}</span>
                </div>

                {/* Body message */}
                <div className="leading-relaxed whitespace-pre-wrap font-sans text-xs">
                  {msg.text}
                </div>

                {/* Grounded Tool Invocation Provenance Card */}
                {!isUser && msg.tool_called && (
                  <div className="mt-3 pt-2.5 border-t border-slate-200">
                    <div className="bg-white rounded-lg border border-teal-200 p-2.5 space-y-1.5 shadow-2xs">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-1.5 text-teal-800 font-bold text-[11px]">
                          <Wrench className="w-3.5 h-3.5 text-teal-600" />
                          <span>Tool Invoked:</span>
                          <code className="bg-teal-50 px-1.5 py-0.5 rounded text-[10px] text-teal-700 font-mono border border-teal-200">
                            {msg.tool_called}
                          </code>
                        </div>

                        <span className="flex items-center text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
                          <ShieldCheck className="w-3 h-3 mr-0.5" />
                          Deterministic
                        </span>
                      </div>

                      {/* Tool arguments */}
                      {msg.tool_arguments && Object.keys(msg.tool_arguments).length > 0 && (
                        <div className="text-[10px] text-slate-500 font-mono bg-slate-50 p-1.5 rounded">
                          <span className="font-semibold text-slate-400 mr-1">Args:</span>
                          {JSON.stringify(msg.tool_arguments)}
                        </div>
                      )}

                      {/* Expandable Raw Data Payload */}
                      {msg.tool_result && (
                        <div>
                          <button
                            onClick={() => togglePayload(msg.id)}
                            className="flex items-center justify-between w-full text-[10px] font-semibold text-teal-700 hover:text-teal-900 pt-1"
                          >
                            <span>Inspect verified tool payload</span>
                            {isPayloadOpen ? (
                              <ChevronUp className="w-3 h-3" />
                            ) : (
                              <ChevronDown className="w-3 h-3" />
                            )}
                          </button>

                          {isPayloadOpen && (
                            <div className="mt-1 bg-slate-900 text-slate-200 p-2 rounded text-[10px] font-mono max-h-48 overflow-y-auto">
                              <pre className="m-0 leading-tight">
                                {JSON.stringify(msg.tool_result, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="flex items-center space-x-2 text-xs text-slate-400 bg-slate-50 p-3 rounded-xl border border-slate-200 max-w-[80%]">
            <Wrench className="w-4 h-4 text-teal-600 animate-spin" />
            <span>Executing deterministic MCP tool query...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div className="p-3 bg-white border-t border-slate-200">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2"
        >
          <input
            type="text"
            placeholder="Ask compliance query (e.g. 3+ major deviations)..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            className="flex-1 px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-teal-500 focus:bg-white text-slate-800 placeholder-slate-400"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="p-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition disabled:opacity-40 disabled:cursor-not-allowed shadow-xs"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        <p className="text-[10px] text-slate-400 text-center mt-1.5 m-0">
          Powered by ClinGuard MCP tools • Zero Hallucination Standard
        </p>
      </div>
    </div>
  );
};
