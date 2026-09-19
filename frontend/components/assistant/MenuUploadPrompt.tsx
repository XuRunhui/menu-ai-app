'use client';

import Link from 'next/link';
import { Camera } from 'lucide-react';
import type { MenuUploadOffer } from '@/lib/api';

/**
 * The dead end turned into the thing Menuist is best at.
 *
 * There is no way to pull a restaurant's menu off the web, so a question like "what's on the
 * menu?" can only be answered from what reviewers happened to mention. Rather than let the
 * assistant trail off, this says so plainly and hands the visitor over to the menu parser with
 * the restaurant name already filled in.
 */
export default function MenuUploadPrompt({ offer }: { offer: MenuUploadOffer }) {
  const nothingFound = offer.reason === 'no_menu_online';
  const name = offer.restaurant_name || 'this restaurant';

  return (
    <div className="rounded-xl border border-dashed border-border bg-accent/40 p-4">
      <p className="text-sm text-foreground leading-relaxed">
        {nothingFound
          ? `${name}'s menu isn't available online.`
          : `That's what reviewers mention — ${name}'s full menu isn't available online.`}{' '}
        If you can photograph it, I&apos;ll read it and translate it.
      </p>

      <Link
        href={`/search?mode=upload&restaurant=${encodeURIComponent(offer.restaurant_name)}`}
        className="mt-3 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm
                   font-medium text-primary-foreground transition-opacity hover:opacity-90"
      >
        <Camera className="w-4 h-4" />
        Upload a menu photo
      </Link>
    </div>
  );
}
