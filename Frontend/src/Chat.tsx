import { type FormEvent, type KeyboardEvent, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ArrowUp, Check, CircleAlert, CircleHelp, Code, Copy, LoaderCircle, MessageCircle, Mic, Square, Volume2 } from 'lucide-react';
import type { AgentResponse } from './api';
import Mascot from './Mascot';
import useDictation from './useDictation';

export type ChatMessage =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; data: AgentResponse }
  | { id: string; role: 'error'; text: string };

const MAX_LENGTH = 2000;

const SUGGESTIONS = [
  'Quels types de puces figurent dans le tableau, et combien de patients chacune ?',
  'Quel allergène compte le plus de patients positifs au seuil de 0,3 ?',
  'En quel mois les pollens de bouleau sont-ils les plus abondants en France ?',
  'À Lyon, quel mois a le risque allergique moyen le plus élevé ?',
];

const numberFormat = new Intl.NumberFormat('fr-FR');

export function formatValue(value: AgentResponse['value']): string {
  if (typeof value === 'number') return numberFormat.format(value);
  return value ?? '';
}

export function spokenAnswer(data: AgentResponse): string {
  if (data.blocked) return data.justification;
  if (data.status === 'abstention') return `Je ne peux pas conclure. ${data.justification}`;
  return `${formatValue(data.value)}. ${data.justification}`;
}

function formatCost(usd: number): string {
  return `${usd.toLocaleString('fr-FR', { minimumFractionDigits: 4, maximumFractionDigits: usd >= 0.01 ? 4 : 6 })} $`;
}

interface Props {
  messages: ChatMessage[];
  loading: boolean;
  elapsed: number;
  speakingId: string | null;
  voiceSupported: boolean;
  onSubmit: (question: string) => void;
  onToggleSpeech: (id: string, text: string) => void;
}

export default function Chat({ messages, loading, elapsed, speakingId, voiceSupported, onSubmit, onToggleSpeech }: Props) {
  const [input, setInput] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const endOfThread = useRef<HTMLDivElement | null>(null);
  const textArea = useRef<HTMLTextAreaElement | null>(null);
  const dictation = useDictation(setInput);

  useEffect(() => {
    endOfThread.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, loading]);

  useEffect(() => {
    if (!loading) textArea.current?.focus();
  }, [loading]);

  // The text area grows with its content, up to the height set in CSS.
  useLayoutEffect(() => {
    const element = textArea.current;
    if (!element) return;
    element.style.height = 'auto';
    element.style.height = `${element.scrollHeight}px`;
  }, [input]);

  const trimmed = input.trim();
  const canSend = !loading && trimmed.length >= 3 && trimmed.length <= MAX_LENGTH;

  const send = (question: string) => {
    if (loading) return;
    dictation.cancel(); // sinon la fin de la dictée remettrait le texte dans la zone de saisie
    onSubmit(question);
    setInput('');
  };

  // Dictating, or installing French for it: the same button stops.
  const dictating = dictation.listening || dictation.installing;

  const toggleDictation = () => {
    if (dictating) dictation.stop();
    else dictation.start(input);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (canSend) send(trimmed);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Escape' && dictating) {
      event.preventDefault();
      dictation.stop();
      return;
    }
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (canSend) send(trimmed);
    }
  };

  const copy = async (id: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1500);
    } catch {
      setCopiedId(null);
    }
  };

  return (
    <div className="chat">
      <div className="thread" aria-live="polite">
        {messages.length === 0 && !loading && (
          <section className="welcome">
            <Mascot state="idle" size="hero" />
            <h1>Bonjour, je suis Christian AI</h1>
            <div className="suggestions">
              {SUGGESTIONS.map((suggestion) => (
                <button key={suggestion} className="suggestion" onClick={() => send(suggestion)}>
                  {suggestion}
                </button>
              ))}
            </div>
          </section>
        )}

        {messages.map((message) => {
          if (message.role === 'user') {
            return (
              <div key={message.id} className="row row--user">
                <div className="bubble bubble--user">{message.text}</div>
              </div>
            );
          }

          if (message.role === 'error') {
            return (
              <div key={message.id} className="row row--agent">
                <Mascot state="idle" size="avatar" decorative />
                <div className="bubble bubble--error" role="alert">
                  <CircleAlert size={16} aria-hidden="true" />
                  <span>{message.text}</span>
                </div>
              </div>
            );
          }

          const { data } = message;
          const speaking = speakingId === message.id;
          return (
            <div key={message.id} className="row row--agent">
              <Mascot state={speaking ? 'speaking' : 'idle'} size="avatar" decorative />
              <article className="bubble bubble--agent">
                <header className="answer__head">
                  <span className="answer__name">Christian AI</span>
                  {data.blocked
                    ? <span className="chip chip--abstain"><MessageCircle size={12} aria-hidden="true" /> Hors sujet</span>
                    : data.status === 'reponse'
                      ? <span className="chip chip--answer"><Check size={12} aria-hidden="true" /> Réponse</span>
                      : <span className="chip chip--abstain"><CircleHelp size={12} aria-hidden="true" /> Abstention</span>}
                </header>

                {/* A question the guard turned away gets a plain reply, not "Je ne peux pas conclure." */}
                {data.blocked
                  ? <p className="answer__reply">{data.justification}</p>
                  : <>
                      {data.status === 'reponse'
                        ? <p className="answer__value">{formatValue(data.value)}</p>
                        : <p className="answer__value answer__value--muted">Je ne peux pas conclure.</p>}
                      <p className="answer__why">{data.justification}</p>
                    </>}

                {data.steps.length > 0 && !data.blocked && (
                  <details className="steps">
                    <summary>
                      <Code size={14} aria-hidden="true" />
                      Raisonnement de l'agent · {data.steps.length} étape{data.steps.length > 1 ? 's' : ''}
                    </summary>
                    <ol>
                      {data.steps.map((step, index) => (
                        <li key={index}><pre><code>{step.code}</code></pre></li>
                      ))}
                    </ol>
                  </details>
                )}

                <footer className="answer__foot">
                  <div className="answer__actions">
                    {voiceSupported && (
                      <button className="ghost" onClick={() => onToggleSpeech(message.id, spokenAnswer(data))}>
                        {speaking ? <><Square size={13} aria-hidden="true" /> Arrêter</> : <><Volume2 size={14} aria-hidden="true" /> Écouter</>}
                      </button>
                    )}
                    <button className="ghost" onClick={() => void copy(message.id, spokenAnswer(data))}>
                      {copiedId === message.id ? <><Check size={14} aria-hidden="true" /> Copié</> : <><Copy size={14} aria-hidden="true" /> Copier</>}
                    </button>
                  </div>
                  {data.blocked && (
                    <span className="answer__meta">Sans appel au modèle · 0 jeton</span>
                  )}
                  {data.reused && (
                    <span className="answer__meta">Réponse reprise d'une trace · 0 jeton</span>
                  )}
                  {!data.reused && data.usage && (
                    <span className="answer__meta">
                      {numberFormat.format(data.usage.input_tokens + data.usage.output_tokens)} jetons
                      {' · '}{formatCost(data.usage.estimated_cost_usd)}
                      {data.duration_s !== null && <>{' · '}{Math.round(data.duration_s)} s</>}
                    </span>
                  )}
                </footer>
              </article>
            </div>
          );
        })}

        {loading && (
          <div className="row row--agent row--typing">
            <Mascot state="thinking" size="avatar" />
            <div className="typing" role="status">
              <span className="typing__dots" aria-hidden="true"><i /><i /><i /></span>
              <span className="typing__text">Christian AI réfléchit…</span>
              <span className="typing__time">{elapsed} s</span>
            </div>
          </div>
        )}
        <div ref={endOfThread} />
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <div className="composer__box">
          <textarea
            ref={textArea}
            rows={1}
            value={input}
            maxLength={MAX_LENGTH}
            placeholder={loading ? 'Christian AI réfléchit…' : dictation.listening ? 'Je vous écoute… parlez en français' : 'Posez une question sur les données'}
            aria-label="Votre question"
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          {dictation.supported && (
            <button
              type="button"
              className={`mic ${dictating ? 'mic--on' : ''}`}
              onClick={toggleDictation}
              disabled={loading && !dictating}
              aria-pressed={dictating}
              aria-label={dictating ? 'Arrêter la dictée' : 'Dicter la question en français'}
              title={dictating
                ? 'Arrêter la dictée (Échap)'
                : dictation.local
                  ? 'Dictée en français sur l\'ordinateur : sans internet, le son reste sur l\'ordinateur'
                  : dictation.canInstall
                    ? 'Dictée en français : au premier clic, le navigateur installe le français pour dicter sans internet'
                    : 'Dictée en français par le service en ligne du navigateur : il faut internet'}
            >
              {dictating ? (
                <>
                  {dictation.installing
                    ? <LoaderCircle size={15} className="spin" aria-hidden="true" />
                    : <Square size={12} fill="currentColor" aria-hidden="true" />}
                  <span>Arrêter</span>
                </>
              ) : <Mic size={18} aria-hidden="true" />}
            </button>
          )}
          <button className="send" type="submit" disabled={!canSend} aria-label="Envoyer la question">
            <ArrowUp size={18} aria-hidden="true" />
          </button>
        </div>
        <p className="composer__hint">
          {dictation.error ? (
            <span className="composer__error" role="alert">{dictation.error}</span>
          ) : dictation.installing ? (
            <span className="composer__listening" role="status">
              Installation du français sur l'ordinateur, une seule fois, pour dicter ensuite sans internet. « Arrêter » ou Échap pour ne pas attendre.
            </span>
          ) : dictation.listening ? (
            <span className="composer__listening" role="status">
              <span className="rec" aria-hidden="true" /> Dictée en français{dictation.local ? ', sans internet' : ''} : « Arrêter » ou Échap pour finir.
            </span>
          ) : (
            <span className="composer__help">Entrée pour envoyer, Maj + Entrée pour aller à la ligne. Une analyse de données, pas un avis médical.</span>
          )}
          <span>{input.length} / {MAX_LENGTH}</span>
        </p>
      </form>
    </div>
  );
}
