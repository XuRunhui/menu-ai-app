'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, MapPin, Send, Sparkles, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils/cn';
import RestaurantSuggestion from './RestaurantSuggestion';
import MenuUploadPrompt from './MenuUploadPrompt';
import FoundMenuCard from './FoundMenuCard';
import {
  sendAssistantMessage,
  type AssistantMessage,
  type AssistantRestaurant,
  type DinerContext,
  type MenuUploadOffer,
  type FoundMenu,
} from '@/lib/api';
import { DEMO_ASSISTANT_PROMPT } from '@/lib/demoTour';

/** Chip text that means "ask the browser where I am" rather than "send this as a message". */
const USE_MY_LOCATION = 'Use my location';

const OPENING: AssistantMessage = {
  role: 'assistant',
  content:
    "Hi — I'm the Menuist dining assistant. What are you in the mood for today? " +
    'A cuisine, a dish, or just a mood like “warm and cheap” all work.',
};

const OPENING_CHIPS = ['Something spicy', 'Comfort food', 'Light and healthy', 'Surprise me'];

type LocationStatus = 'idle' | 'asking' | 'on' | 'denied';

interface SavedChat {
  messages: AssistantMessage[];
  context: DinerContext;
  restaurants: AssistantRestaurant[];
  chips: string[];
  menuOffer: MenuUploadOffer | null;
  foundMenu: FoundMenu | null;
  locationStatus: LocationStatus;
}

/**
 * The conversation, kept in memory for the whole visit, so opening a restaurant and pressing Back
 * picks it up where it was. Nothing is stored: refreshing still clears it, as the footer says.
 */
let savedChat: SavedChat | null = null;

/** Only user and assistant turns are drawn; tool traffic is carried but never shown. */
function isVisible(message: AssistantMessage): boolean {
  return (message.role === 'user' || message.role === 'assistant') && Boolean(message.content);
}

function Bubble({ message }: { message: AssistantMessage }) {
  const isUser = message.role === 'user';
  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap',
          isUser
            ? 'bg-primary text-primary-foreground rounded-br-sm'
            : 'bg-muted text-foreground rounded-bl-sm'
        )}
      >
        {message.content}
      </div>
    </div>
  );
}

export default function ChatPanel() {
  // The whole conversation lives here, including the tool calls the server needs back. Refreshing
  // the page clears it, which is the same guest-mode rule the rest of the app follows.
  const [messages, setMessages] = useState<AssistantMessage[]>(() => savedChat?.messages ?? [OPENING]);
  const [context, setContext] = useState<DinerContext>(() => savedChat?.context ?? {});
  const [restaurants, setRestaurants] = useState<AssistantRestaurant[]>(() => savedChat?.restaurants ?? []);
  const [chips, setChips] = useState<string[]>(() => savedChat?.chips ?? OPENING_CHIPS);
  const [menuOffer, setMenuOffer] = useState<MenuUploadOffer | null>(() => savedChat?.menuOffer ?? null);
  const [foundMenu, setFoundMenu] = useState<FoundMenu | null>(() => savedChat?.foundMenu ?? null);
  const [draft, setDraft] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [locationStatus, setLocationStatus] = useState<LocationStatus>(() =>
    savedChat?.locationStatus === 'on' ? 'on' : 'idle'
  );

  useEffect(() => {
    savedChat = { messages, context, restaurants, chips, menuOffer, foundMenu, locationStatus };
  }, [messages, context, restaurants, chips, menuOffer, foundMenu, locationStatus]);

  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, restaurants, menuOffer, foundMenu, isThinking]);

  const send = async (text: string, nextContext: DinerContext = context, before: AssistantMessage[] = messages) => {
    const trimmed = text.trim();
    if (!trimmed || isThinking) return;

    const history = [...before, { role: 'user' as const, content: trimmed }];
    setMessages(history);
    setDraft('');
    setChips([]);
    setIsThinking(true);
    setError(null);

    try {
      // The opening line is written by the browser, so it is dropped before sending: the server
      // reads the conversation positionally and an extra turn would shift every answer.
      const response = await sendAssistantMessage(history.slice(1), nextContext);
      const next: SavedChat = {
        messages: [OPENING, ...response.messages],
        context: nextContext,
        restaurants: response.restaurants.length > 0 ? response.restaurants : restaurants,
        chips: response.quick_replies,
        // Cleared on every turn: the offer belongs to the place just discussed, and leaving a stale
        // one up would point at a restaurant the conversation has already moved on from.
        menuOffer: response.menu_upload ?? null,
        foundMenu: response.found_menu ?? null,
        locationStatus,
      };
      // Saved here as well as by the effect: if the diner has already left the page, the state
      // updates below do nothing, and the reply would be missing when they come back.
      savedChat = next;
      setMessages(next.messages);
      setChips(next.chips);
      setRestaurants(next.restaurants);
      setMenuOffer(next.menuOffer);
      setFoundMenu(next.foundMenu);
    } catch {
      setError('The assistant is unavailable right now. Please try again in a moment.');
      setMessages(history);
    } finally {
      setIsThinking(false);
    }
  };

  const shareLocation = () => {
    if (!navigator.geolocation) {
      setLocationStatus('denied');
      void send('I would rather type where I am.');
      return;
    }
    setLocationStatus('asking');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const located: DinerContext = {
          ...context,
          latitude: Number(position.coords.latitude.toFixed(4)),
          longitude: Number(position.coords.longitude.toFixed(4)),
        };
        setContext(located);
        setLocationStatus('on');
        void send("I'm here — I've shared my location.", located);
      },
      () => {
        setLocationStatus('denied');
        setChips([]);
      },
      { timeout: 10_000, maximumAge: 300_000 }
    );
  };

  const reset = () => {
    savedChat = null;
    setMessages([OPENING]);
    setRestaurants([]);
    setChips(OPENING_CHIPS);
    setMenuOffer(null);
    setFoundMenu(null);
    setError(null);
    setDraft('');
  };

  // The tour's third step lands here with ?demo=3: a fresh conversation, asked its sample question.
  const router = useRouter();
  const searchParams = useSearchParams();
  const tourAsked = useRef(false);
  useEffect(() => {
    if (searchParams.get('demo') !== '3' || tourAsked.current) return;
    tourAsked.current = true;
    router.replace('/assistant'); // Back or a refresh shouldn't ask again
    queueMicrotask(() => {
      reset();
      void send(DEMO_ASSISTANT_PROMPT, {}, [OPENING]);
    });
    // Runs once, on arrival from the tour.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const visible = messages.filter(isVisible);

  return (
    <div className="flex flex-col h-[calc(100vh-11rem)] max-h-[900px]">
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {visible.map((message, index) => (
          <Bubble key={index} message={message} />
        ))}

        {isThinking && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>Thinking…</span>
          </div>
        )}

        {restaurants.length > 0 && (
          <div className="space-y-2 pt-2">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Places to try
            </p>
            {restaurants.map((place) => (
              <RestaurantSuggestion key={place.place_id} place={place} />
            ))}
          </div>
        )}

        {foundMenu && <FoundMenuCard found={foundMenu} />}
        {menuOffer && <MenuUploadPrompt offer={menuOffer} />}

        {error && <p className="text-sm text-red-600">{error}</p>}
        {locationStatus === 'denied' && (
          <p className="text-xs text-muted-foreground">
            No location shared — just tell me the neighbourhood or city instead.
          </p>
        )}

        <div ref={endRef} />
      </div>

      {chips.length > 0 && !isThinking && (
        <div className="flex flex-wrap gap-2 pt-4">
          {chips.map((chip) => (
            <button
              key={chip}
              onClick={() => (chip === USE_MY_LOCATION ? shareLocation() : send(chip))}
              disabled={chip === USE_MY_LOCATION && locationStatus === 'asking'}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5',
                'text-xs font-medium text-foreground transition-colors',
                'hover:border-primary/40 hover:bg-accent disabled:opacity-50'
              )}
            >
              {chip === USE_MY_LOCATION && <MapPin className="w-3 h-3" />}
              {chip}
            </button>
          ))}
        </div>
      )}

      <form
        className="flex items-center gap-2 pt-4"
        onSubmit={(event) => {
          event.preventDefault();
          void send(draft);
        }}
      >
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Tell me what you feel like eating…"
          disabled={isThinking}
          aria-label="Message the dining assistant"
        />
        <Button type="submit" size="icon" disabled={isThinking || !draft.trim()}>
          <Send className="w-4 h-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" onClick={reset} aria-label="Start over">
          <RotateCcw className="w-4 h-4" />
        </Button>
      </form>

      <p className="pt-2 text-[11px] text-muted-foreground/70 flex items-center gap-1.5">
        <Sparkles className="w-3 h-3" />
        {locationStatus === 'on'
          ? 'Using your location for distances. Nothing is saved — refreshing clears this chat.'
          : 'Nothing is saved — refreshing clears this chat.'}
      </p>
    </div>
  );
}
