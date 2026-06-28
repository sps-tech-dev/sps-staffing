"use client";
/** Scroll-triggered reveal primitives (Framer Motion).
 *  - <Reveal>: fade + slide-up when the element enters the viewport (once).
 *  - <RevealGroup> + <RevealItem>: staggered children.
 *  All respect prefers-reduced-motion: motion is disabled, content shown statically. */
import { motion, useReducedMotion, type Variants } from "framer-motion";
import type { ReactNode } from "react";

// Premium "out-expo"-ish cubic-bezier ease.
const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

export function Reveal({
  children, className, delay = 0, y = 24,
}: { children: ReactNode; className?: string; delay?: number; y?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -12% 0px" }}
      transition={{ duration: 0.6, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

const groupVariants: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1, delayChildren: 0.05 } },
};
const itemVariants: Variants = {
  hidden: { opacity: 0, y: 22 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: EASE } },
};

export function RevealGroup({ children, className }: { children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      variants={reduce ? undefined : groupVariants}
      initial={reduce ? false : "hidden"}
      whileInView={reduce ? undefined : "show"}
      viewport={{ once: true, margin: "0px 0px -10% 0px" }}
    >
      {children}
    </motion.div>
  );
}

export function RevealItem({ children, className }: { children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} variants={reduce ? undefined : itemVariants}>
      {children}
    </motion.div>
  );
}
