"use client";

import * as React from "react";
import { Accessibility } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useA11y } from "@/components/a11y/a11y-provider";

export function A11yPanel() {
  const {
    fontScale, setFontScale,
    reducedMotion, setReducedMotion,
    highContrast, setHighContrast,
  } = useA11y();
  const { theme, setTheme } = useTheme();
  // next-themes is client-only; theme is undefined on first SSR pass.
  // Default to "system" so the radio group has a value before hydration.
  const currentTheme = theme ?? "system";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Tilgjengelighet">
          <Accessibility className="h-4 w-4" />
          <span className="sr-only">Tilgjengelighet</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Tema</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={currentTheme}
          onValueChange={(v) => setTheme(v)}
        >
          <DropdownMenuRadioItem value="system">System</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="light">Lys</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark">Mørk</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="warm">Varm</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>

        <DropdownMenuSeparator />

        <DropdownMenuLabel>Skriftstørrelse</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={fontScale}
          onValueChange={(v) => setFontScale(v as typeof fontScale)}
        >
          <DropdownMenuRadioItem value="default">Normal</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="large">Stor</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="xlarge">Ekstra stor</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>

        <DropdownMenuSeparator />

        <DropdownMenuCheckboxItem
          checked={reducedMotion}
          onCheckedChange={setReducedMotion}
        >
          Reduser animasjoner
        </DropdownMenuCheckboxItem>
        <DropdownMenuCheckboxItem
          checked={highContrast}
          onCheckedChange={setHighContrast}
        >
          Høy kontrast
        </DropdownMenuCheckboxItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
