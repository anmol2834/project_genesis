'use client';

import * as React from 'react';
import { useServerInsertedHTML } from 'next/navigation';
import createCache from '@emotion/cache';
import type { EmotionCache, Options as OptionsOfCreateCache } from '@emotion/cache';
import { CacheProvider } from '@emotion/react';

export type NextAppDirEmotionCacheProviderProps = {
  options: Omit<OptionsOfCreateCache, 'insertionPoint'>;
  children: React.ReactNode;
};

/**
 * Emotion cache provider for Next.js App Router.
 * Flushes server-rendered emotion styles into the HTML stream so the
 * client hydration sees identical markup and the mismatch error is gone.
 *
 * Based on the official MUI + Next.js App Router example:
 * https://github.com/mui/material-ui/tree/master/examples/material-ui-nextjs-ts
 */
export default function NextAppDirEmotionCacheProvider(
  props: NextAppDirEmotionCacheProviderProps,
) {
  const { options, children } = props;

  const [{ cache, flush }] = React.useState(() => {
    const emotionCache = createCache(options);
    emotionCache.compat = true;

    const prevInsert = emotionCache.insert.bind(emotionCache);
    let inserted: string[] = [];

    emotionCache.insert = (...args) => {
      const serialized = args[1];
      if (emotionCache.inserted[serialized.name] === undefined) {
        inserted.push(serialized.name);
      }
      return prevInsert(...args);
    };

    const flushCache = () => {
      const prevInserted = inserted;
      inserted = [];
      return prevInserted;
    };

    return { cache: emotionCache, flush: flushCache };
  });

  useServerInsertedHTML(() => {
    const names = flush();
    if (names.length === 0) return null;

    let styles = '';
    for (const name of names) {
      styles += cache.inserted[name];
    }

    return (
      <style
        key={cache.key}
        data-emotion={`${cache.key} ${names.join(' ')}`}
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: styles }}
      />
    );
  });

  return <CacheProvider value={cache}>{children}</CacheProvider>;
}
