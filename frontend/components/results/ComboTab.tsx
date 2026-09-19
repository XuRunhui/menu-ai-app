'use client';

import { useMemo, useState } from 'react';
import { BookOpen, Globe2, Lightbulb, Loader2, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { getCombos, type ComboDishInput } from '@/lib/api';
import type { Combo } from '@/lib/types';
import { useAppContext } from '@/context/AppContext';

type ComboState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'done'; combos: Combo[]; cuisine: string; attribution: string }
  | { status: 'error'; message: string };

function ComboCard({ combo, displayName }: { combo: Combo; displayName: (name: string) => string }) {
  return (
    <article className="rounded-2xl border border-border bg-card p-6 space-y-4">
      <div className="space-y-1">
        <p className="text-xs font-medium tracking-widest uppercase text-primary/70">
          {combo.dishes.map(displayName).join('  +  ')}
        </p>
        <h3 className="font-display text-2xl font-light text-foreground">{combo.title}</h3>
      </div>

      <p className="text-sm leading-relaxed text-foreground/90">{combo.explanation}</p>

      {combo.cultural_note && (
        <p className="flex gap-2 text-sm text-muted-foreground">
          <Globe2 className="w-4 h-4 mt-0.5 shrink-0 text-primary/70" />
          {combo.cultural_note}
        </p>
      )}

      {combo.tip && (
        <p className="flex gap-2 text-sm text-muted-foreground">
          <Lightbulb className="w-4 h-4 mt-0.5 shrink-0 text-amber-500" />
          {combo.tip}
        </p>
      )}

      {combo.dish_profiles.length > 0 && (
        <dl className="grid gap-1.5 text-xs">
          {combo.dish_profiles.map((profile, index) => (
            // Menus repeat names ("Classic" burger, "Classic" poutine), so the position keeps keys unique.
            <div key={`${index}-${profile.name}`} className="flex flex-wrap gap-x-2">
              <dt className="font-medium text-foreground">{displayName(profile.name)}</dt>
              <dd className="text-muted-foreground">
                {[profile.role.replace(/_/g, ' '), profile.tastes.slice(0, 3).join(', '),
                  profile.textures.slice(0, 2).join(', '), profile.colors.slice(0, 2).join(', ')]
                  .filter(Boolean).join(' · ')}
              </dd>
            </div>
          ))}
        </dl>
      )}

      <div className="flex flex-wrap gap-1.5">
        {combo.reasons.map((reason, index) => (
          <Badge key={`${index}-${reason}`} variant="recommended">{reason}</Badge>
        ))}
        {combo.pairings.slice(0, 3).map((pairing, index) => (
          <Badge key={`${index}-${pairing.a}-${pairing.b}`} variant="muted" title="Ingredients that co-occur in recipes more than chance">
            {pairing.a} × {pairing.b}
          </Badge>
        ))}
        {combo.shared_compounds.length > 0 && (
          <Badge variant="outline" title="Flavor compounds found in both ingredients">
            shared compounds: {combo.shared_compounds.join(', ')}
          </Badge>
        )}
      </div>

      {combo.sources.length > 0 && (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer flex items-center gap-1.5 hover:text-foreground">
            <BookOpen className="w-3.5 h-3.5" /> Food-culture references
          </summary>
          <ul className="mt-2 space-y-2">
            {combo.sources.map((source, i) => (
              <li key={i} className="border-l-2 border-border pl-3">
                <p className="italic line-clamp-3">“{source.excerpt}…”</p>
                <p className="mt-1">
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                      {source.title}
                    </a>
                  ) : source.title}
                  {' · '}{source.license}
                </p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

export default function ComboTab() {
  const { parsedMenu, popularDishes, targetLanguage, restaurant, placeDetails, menuSources } = useAppContext();
  const combined =
    menuSources && menuSources.placeId === placeDetails?.place?.place_id ? menuSources.combined : null;
  // The fullest menu available: an upload, else everything the sources found, else review dishes.
  const menu = parsedMenu?.menu?.length ? parsedMenu : combined?.menu.menu.length ? combined.menu : null;
  const [state, setState] = useState<ComboState>({ status: 'idle' });

  const { dishes, translations } = useMemo(() => {
    const translations = new Map<string, string>();
    let dishes: ComboDishInput[] = [];
    if (menu?.menu?.length) {
      dishes = menu.menu.flatMap((category) =>
        category.items.map((item) => {
          if (item.name_translated) translations.set(item.name, item.name_translated);
          return { name: item.name, description: item.description, category: category.category };
        })
      );
    } else {
      dishes = popularDishes.map((dish) => ({ name: dish.name, description: null, category: null }));
    }
    return { dishes, translations };
  }, [menu, popularDishes]);

  const displayName = (name: string) =>
    targetLanguage && translations.get(name) ? `${translations.get(name)} (${name})` : name;

  const suggest = async () => {
    setState({ status: 'loading' });
    try {
      const result = await getCombos(dishes, 3, restaurant?.name);
      setState({ status: 'done', combos: result.combos, cuisine: result.cuisine, attribution: result.attribution });
    } catch (err) {
      setState({ status: 'error', message: err instanceof Error ? err.message : 'Could not load combos.' });
    }
  };

  if (state.status === 'idle' || state.status === 'loading' || state.status === 'error') {
    return (
      <div className="flex flex-col items-center justify-center gap-5 py-20 text-center">
        <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-accent text-primary">
          <Sparkles className="w-7 h-7" strokeWidth={1.5} />
        </div>
        <div className="space-y-2">
          <h3 className="font-display text-2xl font-light text-foreground">Combo Recommendations</h3>
          <p className="text-muted-foreground text-sm max-w-md leading-relaxed">
            Find dishes on this menu that go well together: balanced tastes, contrasting textures and colors, and
            how the menu&apos;s food culture usually combines dishes.
          </p>
        </div>
        <Button onClick={suggest} disabled={dishes.length < 2 || state.status === 'loading'} className="gap-2">
          {state.status === 'loading' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {state.status === 'loading' ? 'Tasting the menu… (about 15 seconds)' : 'Suggest combos'}
        </Button>
        {dishes.length < 2 && <p className="text-xs text-muted-foreground">Needs at least two dishes.</p>}
        {state.status === 'error' && <p className="text-sm text-red-700">{state.message}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {state.cuisine && (
        <p className="text-xs text-muted-foreground">Menu style: <span className="text-foreground">{state.cuisine}</span></p>
      )}
      {state.combos.length === 0 ? (
        <p className="text-center text-sm text-muted-foreground py-16">
          No good combos found for these dishes. Menus with descriptions work best.
        </p>
      ) : (
        state.combos.map((combo) => (
          <ComboCard key={combo.dishes.join('|')} combo={combo} displayName={displayName} />
        ))
      )}
      <p className="text-center text-xs text-muted-foreground/70 pt-2">{state.attribution}</p>
    </div>
  );
}
