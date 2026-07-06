"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { PleEventGrid } from "@/components/ple-event-grid";
import { cn } from "@/lib/utils";

type PlePickerDialogProps = {
  triggerClassName?: string;
};

export function PlePickerDialog({ triggerClassName }: PlePickerDialogProps) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className={triggerClassName}
          aria-expanded={open}
        >
          PLE
        </Button>
      </DialogTrigger>
      <DialogContent
        className={cn(
          "max-h-[min(90dvh,820px)] overflow-y-auto border-stone-300 dark:border-stone-700 bg-stone-50 dark:bg-stone-900 text-stone-900 dark:text-stone-100 sm:max-w-3xl",
        )}
        showCloseButton
      >
        <DialogHeader>
          <DialogTitle className="text-center text-xl text-stone-50">
            월별 PLE
          </DialogTitle>
          <DialogDescription className="text-center text-sm text-stone-400">
            예측할 이벤트를 선택하세요
          </DialogDescription>
        </DialogHeader>
        <PleEventGrid variant="large" onNavigate={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}
