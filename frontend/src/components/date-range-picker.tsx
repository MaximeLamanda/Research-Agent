"use client";

import * as React from "react";
import { format, parseISO } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { type DateRange } from "react-day-picker";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

function toDateRange(startDate?: string, endDate?: string): DateRange | undefined {
  if (!startDate && !endDate) {
    return undefined;
  }

  return {
    from: startDate ? parseISO(startDate) : undefined,
    to: endDate ? parseISO(endDate) : undefined,
  };
}

function toIsoDate(date?: Date): string | null {
  if (!date) {
    return null;
  }

  return format(date, "yyyy-MM-dd");
}

interface DatePickerWithRangeProps {
  id?: string;
  label?: string;
  startDate?: string;
  endDate?: string;
  onChange?: (range: { startDate: string | null; endDate: string | null }) => void;
  placeholder?: string;
  className?: string;
}

export function DatePickerWithRange({
  id = "date-picker-range",
  label = "Date Picker Range",
  startDate,
  endDate,
  onChange,
  placeholder = "Pick a date",
  className,
}: DatePickerWithRangeProps) {
  const date = toDateRange(startDate, endDate);

  return (
    <Field className={cn("w-full", className)}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Popover>
        <PopoverTrigger
          id={id}
          render={
            <Button variant="outline" className="w-full justify-start px-2.5 font-normal" />
          }
        >
          <CalendarIcon />
          {date?.from ? (
            date.to ? (
              <>
                {format(date.from, "LLL dd, y")} - {format(date.to, "LLL dd, y")}
              </>
            ) : (
              format(date.from, "LLL dd, y")
            )
          ) : (
            <span>{placeholder}</span>
          )}
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="range"
            defaultMonth={date?.from}
            selected={date}
            onSelect={(range) => {
              onChange?.({
                startDate: toIsoDate(range?.from),
                endDate: toIsoDate(range?.to),
              });
            }}
            numberOfMonths={2}
          />
        </PopoverContent>
      </Popover>
    </Field>
  );
}

export { DatePickerWithRange as DateRangePicker };
