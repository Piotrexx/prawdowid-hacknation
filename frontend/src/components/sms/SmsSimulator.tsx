"use client";

import { FlaskConical } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/Notice";
import { SmsChat } from "./SmsChat";

const DEFAULT_PHONE = "+48500100200";
const PHONE_PATTERN = /^\+?[0-9]{6,15}$/;

export function SmsSimulator() {
  const [phone, setPhone] = useState(DEFAULT_PHONE);
  const [phoneInput, setPhoneInput] = useState(DEFAULT_PHONE);
  const [phoneError, setPhoneError] = useState<string | null>(null);

  function applyPhone() {
    const candidate = phoneInput.replace(/[\s-]/g, "");
    if (!PHONE_PATTERN.test(candidate)) {
      setPhoneError("Podaj numer z samych cyfr, na przykład +48500100200.");
      return;
    }
    setPhoneError(null);
    setPhoneInput(candidate);
    setPhone(candidate);
  }

  return (
    <div className="space-y-6">
      <Notice tone="info" icon={FlaskConical} title="To jest symulator. Nie wysyła prawdziwych SMS-ów.">
        <p>
          Pokazuje, jak Prawdowid odpowiada w kanale SMS i WhatsApp. Korzysta z tej
          samej logiki sprawdzania co strona WWW. Wiadomości trafiają do serwera w
          formacie zgodnym z webhookiem Twilio.
        </p>
      </Notice>

      <form
        noValidate
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          applyPhone();
        }}
      >
        <label htmlFor="sms-numer" className="block font-semibold">
          Numer nadawcy (symulowany)
        </label>
        <div className="flex flex-wrap gap-2">
          <input
            id="sms-numer"
            type="tel"
            inputMode="tel"
            autoComplete="off"
            value={phoneInput}
            aria-invalid={phoneError ? true : undefined}
            aria-describedby={phoneError ? "sms-numer-blad" : undefined}
            onChange={(event) => setPhoneInput(event.target.value)}
            className="min-h-11 w-56 max-w-full rounded-lg border border-line-strong bg-surface px-3"
          />
          <Button type="submit">Zmień numer</Button>
        </div>
        {phoneError ? (
          <p id="sms-numer-blad" role="alert" className="font-medium text-bad-fg">
            {phoneError}
          </p>
        ) : null}
      </form>

      <SmsChat key={phone} phone={phone} />

      <p id="sms-pomoc" className="text-center text-muted">
        Enter wysyła wiadomość. Shift+Enter dodaje nową linię.
      </p>
    </div>
  );
}
