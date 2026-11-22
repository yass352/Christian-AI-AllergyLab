import { useCallback, useEffect, useRef, useState } from 'react';

// Dictation in French with the browser's own speech recognition (Web Speech API): no
// library, no call to our model, nothing to pay.
// A recent Chrome can recognise French on the computer itself. The first click asks it
// to install the French language pack (a one-time download, so internet is needed once);
// after that, dictation works without internet and the audio never leaves the computer.
// Browsers that cannot do this (Edge, Brave, an older Chrome) send the audio to their own
// online speech service, which needs internet every time.

const LANG = 'fr-FR';
const ON_DEVICE = { langs: [LANG], processLocally: true };

interface Alternative { transcript: string }
interface Result { isFinal: boolean; 0: Alternative }
interface ResultEvent { resultIndex: number; results: ArrayLike<Result> }
interface ErrorEvent { error: string }

interface Recognizer {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  processLocally?: boolean;
  onresult: ((event: ResultEvent) => void) | null;
  onerror: ((event: ErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

interface RecognizerClass {
  new (): Recognizer;
  // Both static, in the current Web Speech API spec; absent from browsers without on-device recognition.
  available?: (options: typeof ON_DEVICE) => Promise<string>;
  install?: (options: typeof ON_DEVICE) => Promise<boolean>;
}

function recognizerClass(): RecognizerClass | null {
  const scope = window as unknown as { SpeechRecognition?: RecognizerClass; webkitSpeechRecognition?: RecognizerClass };
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null;
}

const ERRORS: Record<string, string> = {
  'not-allowed': 'Micro refusé : autorisez-le dans les réglages du navigateur, puis réessayez.',
  'service-not-allowed': 'Le navigateur refuse la dictée sur cette page.',
  'audio-capture': 'Aucun micro trouvé : branchez-en un, puis réessayez.',
  'no-speech': 'Aucune parole entendue : réessayez en parlant plus près du micro.',
  network: 'Ce navigateur dicte avec un service en ligne qu\'il n\'a pas pu joindre. Pour dicter sans internet, ouvrez l\'interface dans Chrome à jour ; sinon, tapez la question.',
  'language-not-supported': 'Ce navigateur ne sait pas dicter en français : ouvrez l\'interface dans Chrome à jour, ou tapez la question.',
};

// When on-device French fails with one of these, dictation restarts at once on the online service.
const TRY_ONLINE = new Set(['language-not-supported', 'service-not-allowed', 'network']);

function join(base: string, spoken: string): string {
  const said = spoken.trim();
  if (!said) return base;
  return base.trim() ? `${base.trimEnd()} ${said}` : said;
}

export interface Dictation {
  supported: boolean;
  /** True when French is installed on the computer: dictation works offline, the audio stays local. */
  local: boolean;
  /** True when the browser could install French on the computer at the first click. */
  canInstall: boolean;
  /** True while the browser downloads French, the first time only. */
  installing: boolean;
  listening: boolean;
  error: string | null;
  start: (base: string) => void;
  stop: () => void;
  /** Stops at once and drops what was being dictated, for example when the question is sent. */
  cancel: () => void;
}

export default function useDictation(setText: (text: string) => void): Dictation {
  const [supported, setSupported] = useState(false);
  const [local, setLocal] = useState(false);
  const [canInstall, setCanInstall] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const current = useRef<Recognizer | null>(null);
  const discard = useRef(false);
  const onDeviceFailed = useRef(false);
  const waitingInstall = useRef(false);
  const forceStop = useRef<number | undefined>(undefined);

  useEffect(() => {
    const Klass = recognizerClass();
    setSupported(Klass !== null);
    setCanInstall(Boolean(Klass?.install));
    // Until this page has called install() once, browsers answer "downloadable" whatever
    // is installed (a privacy rule of the spec): only "available" is taken as a yes.
    Klass?.available?.(ON_DEVICE)
      .then((status) => setLocal(status === 'available'))
      .catch(() => setLocal(false));
    return () => current.current?.abort();
  }, []);

  const start = useCallback((base: string) => {
    const Klass = recognizerClass();
    if (!Klass || current.current || installing) return;
    discard.current = false;
    setError(null);

    const launch = (onDevice: boolean) => {
      const recognizer = new Klass();
      recognizer.lang = LANG;
      recognizer.continuous = true;
      recognizer.interimResults = true;
      if (onDevice) recognizer.processLocally = true;

      let finalText = '';
      let heard = false;
      let failure: string | null = null;
      recognizer.onresult = (event) => {
        heard = true;
        let interim = '';
        for (let index = event.resultIndex; index < event.results.length; index++) {
          const result = event.results[index];
          if (result.isFinal) finalText += `${result[0].transcript} `;
          else interim += result[0].transcript;
        }
        setText(join(base, finalText + interim));
      };
      recognizer.onerror = (event) => { failure = event.error; };
      recognizer.onend = () => {
        window.clearTimeout(forceStop.current);
        current.current = null;
        if (onDevice && !heard && failure && TRY_ONLINE.has(failure) && !discard.current) {
          onDeviceFailed.current = true;
          setLocal(false);
          launch(false);
          return;
        }
        setListening(false);
        if (failure && failure !== 'aborted') setError(ERRORS[failure] ?? 'La dictée s\'est arrêtée.');
        if (!discard.current) setText(join(base, finalText));
        discard.current = false;
      };

      current.current = recognizer;
      try {
        recognizer.start();
        setListening(true);
      } catch {
        current.current = null;
        setListening(false);
        setError('La dictée n\'a pas pu démarrer.');
      }
    };

    if (local || !Klass.install || onDeviceFailed.current) {
      launch(local && !onDeviceFailed.current);
      return;
    }
    // First click: ask the browser to install French on the computer. install() runs inside
    // the click, because the browser downloads a language pack only after a user gesture.
    setInstalling(true);
    waitingInstall.current = true;
    Klass.install(ON_DEVICE)
      .catch(() => false)
      .then((installed) => {
        if (!waitingInstall.current) return; // the user pressed Stop meanwhile
        waitingInstall.current = false;
        setInstalling(false);
        if (!installed) onDeviceFailed.current = true;
        setLocal(installed);
        if (!discard.current) launch(installed);
        discard.current = false;
      });
  }, [installing, local, setText]);

  // Stop: keeps what was dictated. Works in every state, so the user is never stuck.
  const stop = useCallback(() => {
    if (waitingInstall.current) {
      // Stopped while French was downloading: give up waiting, and dictate online at the next click.
      waitingInstall.current = false;
      onDeviceFailed.current = true;
      setInstalling(false);
      return;
    }
    const recognizer = current.current;
    if (!recognizer) { setListening(false); return; }
    recognizer.stop();
    // stop() waits for the last words; if the browser never answers, end it anyway.
    window.clearTimeout(forceStop.current);
    forceStop.current = window.setTimeout(() => {
      if (current.current !== recognizer) return;
      recognizer.abort();
      current.current = null;
      setListening(false);
    }, 1500);
  }, []);

  // Cancel: stops at once and drops what was being dictated (the question has just been sent).
  const cancel = useCallback(() => {
    discard.current = true;
    if (waitingInstall.current) {
      waitingInstall.current = false;
      setInstalling(false);
    }
    current.current?.abort();
  }, []);

  return { supported, local, canInstall, installing, listening, error, start, stop, cancel };
}
