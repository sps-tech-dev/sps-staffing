"use client";
/** Full-viewport video-background hero.
 *  - <video autoPlay muted loop playsInline> with mp4 + webm sources and a poster.
 *  - On small screens OR when the user prefers reduced motion, the video is NOT
 *    mounted — the poster image is shown instead (perf + accessibility).
 *  - A dark gradient overlay (deeper at the bottom) keeps light text readable. */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Image from "next/image";

const POSTER = "/video/staffing-hero-poster.jpg";

export function VideoHero({
  children, minHeight = "min-h-[100svh]",
}: { children: ReactNode; minHeight?: string }) {
  const [playVideo, setPlayVideo] = useState(false);

  useEffect(() => {
    // Decide on the client: skip the video on small viewports or reduced-motion.
    const motionOk = window.matchMedia("(prefers-reduced-motion: no-preference)").matches;
    const bigEnough = window.matchMedia("(min-width: 768px)").matches;
    if (motionOk && bigEnough) setPlayVideo(true);
  }, []);

  return (
    <section className={`relative isolate flex ${minHeight} items-center overflow-hidden bg-sps-navy`}>
      {/* Background: poster always; video layered on top once allowed */}
      <div className="absolute inset-0 -z-10">
        <Image
          src={POSTER}
          alt=""
          aria-hidden
          fill
          priority
          sizes="100vw"
          className="object-cover"
        />
        {playVideo && (
          <video
            className="absolute inset-0 h-full w-full object-cover"
            autoPlay
            muted
            loop
            playsInline
            poster={POSTER}
            aria-hidden
          >
            <source src="/video/staffing-hero.webm" type="video/webm" />
            <source src="/video/staffing-hero.mp4" type="video/mp4" />
          </video>
        )}
      </div>

      {/* Readability overlay — dark, deeper toward the bottom, plus a left-side wash */}
      <div
        className="absolute inset-0 -z-10 bg-gradient-to-b from-sps-navy/55 via-sps-navy/45 to-sps-navy/85"
        aria-hidden
      />
      <div
        className="absolute inset-0 -z-10 bg-gradient-to-r from-sps-navy/55 to-transparent"
        aria-hidden
      />

      <div className="mx-auto w-full max-w-6xl px-6 py-28 sm:py-32">{children}</div>
    </section>
  );
}
