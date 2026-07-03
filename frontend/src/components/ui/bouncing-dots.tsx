"use client";

import { cva } from "class-variance-authority";
import { HTMLMotionProps, motion } from "motion/react";

import { cn } from "@/lib/utils";

const bouncingDotsVariant = cva("flex gap-2 items-center justify-center", {
  variants: {
    messagePlacement: {
      bottom: "flex-col",
      right: "flex-row",
      left: "flex-row-reverse",
    },
  },
  defaultVariants: {
    messagePlacement: "bottom",
  },
});

export interface BouncingDotsProps {
  dots?: number;
  message?: string;
  messagePlacement?: "bottom" | "left" | "right";
  /** Bounce amplitude in px (dots move up by this amount). Default 20. */
  bounceHeight?: number;
  /** Classes applied to each dot (size, color…). */
  dotClassName?: string;
  /** Classes applied to the wrapper holding the dots (e.g. to override the gap). */
  containerClassName?: string;
  /** Accessible label announced to screen readers. Default "Loading". */
  label?: string;
}

export function BouncingDots({
  dots = 3,
  message,
  messagePlacement = "bottom",
  bounceHeight = 20,
  dotClassName,
  containerClassName,
  label = "Loading",
  className,
  ...props
}: HTMLMotionProps<"div"> & BouncingDotsProps) {
  return (
    <motion.div
      role="status"
      aria-label={label}
      className={cn(bouncingDotsVariant({ messagePlacement }), className)}
      {...props}
    >
      <div className={cn("flex gap-2 items-center justify-center", containerClassName)}>
        {Array.from({ length: dots }, (_, index) => (
          <motion.div
            key={index}
            className={cn("w-3 h-3 bg-foreground rounded-full", dotClassName)}
            animate={{ y: [0, -bounceHeight, 0] }}
            transition={{
              duration: 0.6,
              repeat: Infinity,
              delay: index * 0.2,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
      {message && <div>{message}</div>}
    </motion.div>
  );
}
