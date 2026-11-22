import { useCallback, useEffect, useRef, useState } from 'react';
import { Database, Info, Menu, MessageSquare, Plus, X } from 'lucide-react';
import AboutPage from './AboutPage';
import { askAgent } from './api';
import Chat, { type ChatMessage } from './Chat';
import DataPage from './DataPage';
import Mascot, { type MascotState, preloadMascot } from './Mascot';

type Page = 'assistant' | 'data' | 'about';

const PAGES: { id: Page; label: string; icon: typeof MessageSquare }[] = [
  { id: 'assistant', label: 'Assistant', icon: MessageSquare },
  { id: 'data', label: 'Données', icon: Database },
  { id: 'about', label: 'À propos', icon: Info },
];

const STATUS: Record<MascotState, string> = {
  idle: 'En ligne',
  thinking: 'réfléchit…',
  speaking: 'lit sa réponse à voix haute',
};

const integer = new Intl.NumberFormat('fr-FR');

export default function App() {
  const [page, setPage] = useState<Page>('assistant');
  const [menuOpen, setMenuOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    preloadMascot();
    setVoiceSupported('speechSynthesis' in window);
    return () => {
      activeRequest.current?.abort();
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    };
  }, []);

  // Seconds since the question left, shown beside "Christian AI réfléchit…".
  useEffect(() => {
    if (!loading) return;
    const started = Date.now();
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [loading]);

  const stopSpeech = useCallback(() => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    setSpeakingId(null);
  }, []);

  const toggleSpeech = useCallback((id: string, text: string) => {
    if (!('speechSynthesis' in window)) return;
    if (speakingId === id) { stopSpeech(); return; }
    stopSpeech();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'fr-FR';
    // A French voice, installed on the computer when there is one: the right accent, and no internet needed.
    const french = window.speechSynthesis.getVoices().filter((voice) => voice.lang.toLowerCase().startsWith('fr'));
    const voice = french.find((candidate) => candidate.localService) ?? french[0];
    if (voice) utterance.voice = voice;
    utterance.rate = 0.97;
    utterance.onstart = () => setSpeakingId(id);
    utterance.onend = () => setSpeakingId(null);
    utterance.onerror = () => setSpeakingId(null);
    window.speechSynthesis.speak(utterance);
  }, [speakingId, stopSpeech]);

  const submit = useCallback(async (question: string) => {
    if (loading) return;
    stopSpeech();
    setPage('assistant');
    setLoading(true);
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'user', text: question }]);

    const controller = new AbortController();
    activeRequest.current = controller;
    try {
      const data = await askAgent(question, controller.signal);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', data }]);
    } catch (error: unknown) {
      if (controller.signal.aborted) return;
      const text = error instanceof Error ? error.message : 'Une erreur inattendue est survenue.';
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'error', text }]);
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
      setLoading(false);
    }
  }, [loading, stopSpeech]);

  const go = (next: Page) => {
    stopSpeech();
    setPage(next);
    setMenuOpen(false);
  };

  const newConversation = () => {
    if (loading) return;
    stopSpeech();
    setMessages([]);
    go('assistant');
  };

  const session = messages.reduce(
    (total, message) => {
      if (message.role !== 'assistant' || !message.data.usage) return total;
      const usage = message.data.usage;
      return { tokens: total.tokens + usage.input_tokens + usage.output_tokens, cost: total.cost + usage.estimated_cost_usd };
    },
    { tokens: 0, cost: 0 },
  );

  const mascotState: MascotState = loading ? 'thinking' : speakingId ? 'speaking' : 'idle';
  const title = PAGES.find((item) => item.id === page)?.label ?? '';

  return (
    <div className="app">
      <aside className={`sidebar ${menuOpen ? 'sidebar--open' : ''}`} aria-label="Navigation">
        <div className="sidebar__top">
          <button className="brand" onClick={() => go('assistant')}>
            <span className="brand__logo"><img src="/images/logo.avif" alt="" /></span>
            <span className="brand__text"><strong>Christian AI</strong><small>AllergyLab </small></span>
          </button>
          <button className="icon-button sidebar__close" aria-label="Fermer le menu" onClick={() => setMenuOpen(false)}><X size={18} /></button>
        </div>

        <button className="new-chat" onClick={newConversation} disabled={loading}>
          <Plus size={16} aria-hidden="true" /> Nouvelle conversation
        </button>

        <nav className="nav">
          {PAGES.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav__item ${page === id ? 'nav__item--active' : ''}`} onClick={() => go(id)} aria-current={page === id ? 'page' : undefined}>
              <Icon size={16} aria-hidden="true" /> {label}
            </button>
          ))}
        </nav>

        <div className="sidebar__foot">
          <span className="local"><span className="dot" aria-hidden="true" /> Mode local · 127.0.0.1</span>
          <span>Session : {integer.format(session.tokens)} jetons · {session.cost.toLocaleString('fr-FR', { maximumFractionDigits: 4 })} $</span>
        </div>
      </aside>

      {menuOpen && <button className="overlay" aria-label="Fermer le menu" onClick={() => setMenuOpen(false)} />}

      <main className="main">
        <header className="topbar">
          <button className="icon-button menu-button" aria-label="Ouvrir le menu" onClick={() => setMenuOpen(true)}><Menu size={20} /></button>
          {page === 'assistant' ? (
            <div className="presence">
              <Mascot state={mascotState} size="header" />
              <div className="presence__text">
                <strong>Christian AI</strong>
                <span className={`presence__status presence__status--${mascotState}`}>{STATUS[mascotState]}</span>
              </div>
            </div>
          ) : (
            <strong className="topbar__title">{title}</strong>
          )}
        </header>

        {page === 'assistant' && (
          <Chat
            messages={messages}
            loading={loading}
            elapsed={elapsed}
            speakingId={speakingId}
            voiceSupported={voiceSupported}
            onSubmit={(question) => void submit(question)}
            onToggleSpeech={toggleSpeech}
          />
        )}
        {page === 'data' && <DataPage />}
        {page === 'about' && <AboutPage />}
      </main>
    </div>
  );
}
