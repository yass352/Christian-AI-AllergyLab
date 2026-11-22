import { useEffect, useState } from 'react';

export type MascotState = 'idle' | 'thinking' | 'speaking';
type MascotSize = 'avatar' | 'header' | 'hero';

const ANIMATED: Record<MascotState, string> = {
  idle: '/images/mascot-idle.avif',
  thinking: '/images/mascot-thinking.gif',
  speaking: '/images/mascot-speaking.gif',
};

// Still images for people who ask their system for less motion.
const STILL: Record<MascotState, string> = {
  idle: '/images/mascot-idle.avif',
  thinking: '/images/mascot-thinking.avif',
  speaking: '/images/mascot-idle.avif',
};

const LABELS: Record<MascotState, string> = {
  idle: 'Christian AI est prêt',
  thinking: 'Christian AI réfléchit',
  speaking: 'Christian AI lit sa réponse',
};

/** Loads the animated frames ahead of time, so switching state never flashes an empty avatar. */
export function preloadMascot(): void {
  for (const src of [...Object.values(ANIMATED), ...Object.values(STILL)]) {
    const image = new Image();
    image.src = src;
  }
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return reduced;
}

interface Props {
  state: MascotState;
  size?: MascotSize;
  decorative?: boolean;
}

export default function Mascot({ state, size = 'hero', decorative = false }: Props) {
  const reduced = usePrefersReducedMotion();
  const src = reduced ? STILL[state] : ANIMATED[state];
  return (
    <span
      className={`mascot mascot--${size} mascot--${state}`}
      role={decorative ? undefined : 'img'}
      aria-label={decorative ? undefined : LABELS[state]}
      aria-hidden={decorative ? true : undefined}
    >
      <span className="mascot__face">
        <img src={src} alt="" />
      </span>
      {state === 'thinking' && (
        <span className="mascot__thought" aria-hidden="true">
          <span className="mascot__thought-trail" />
          <span className="mascot__thought-cloud"><i /><i /><i /></span>
        </span>
      )}
      {state === 'speaking' && <span className="mascot__wave" aria-hidden="true" />}
    </span>
  );
}
