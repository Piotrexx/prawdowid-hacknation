export interface PiiResult {
  text: string;
  masked: string[];
}

function validatePesel(digits: string): boolean {
  if (digits.length !== 11) return false;
  const weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3];
  let sum = 0;
  for (let i = 0; i < 10; i++) {
    sum += parseInt(digits[i]) * weights[i];
  }
  return (10 - (sum % 10)) % 10 === parseInt(digits[10]);
}

interface PiiRule {
  pattern: RegExp;
  replacement: string;
  label: string;
  validate?: (match: string) => boolean;
}

const PII_RULES: PiiRule[] = [
  {
    pattern: /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g,
    replacement: "[ADRES_EMAIL]",
    label: "adres e-mail",
  },
  {
    pattern: /\b\d{11}\b/g,
    replacement: "[PESEL]",
    label: "numer PESEL",
    validate: validatePesel,
  },
  {
    // +48 or 0048 prefix, then 9 digits (optionally grouped)
    pattern: /(?:\+48|0048)[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{3}\b/g,
    replacement: "[NUMER_TELEFONU]",
    label: "numer telefonu",
  },
  {
    // Standalone 9-digit Polish number with separators: 123 456 789 or 123-456-789
    pattern: /\b\d{3}[\s\-]\d{3}[\s\-]\d{3}\b/g,
    replacement: "[NUMER_TELEFONU]",
    label: "numer telefonu",
  },
  {
    pattern:
      /\b(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b/g,
    replacement: "[ADRES_IP]",
    label: "adres IP",
  },
];

export function maskPii(input: string): PiiResult {
  let text = input;
  const maskedSet = new Set<string>();

  for (const rule of PII_RULES) {
    rule.pattern.lastIndex = 0;
    text = text.replace(rule.pattern, (match) => {
      if (rule.validate && !rule.validate(match)) return match;
      maskedSet.add(rule.label);
      return rule.replacement;
    });
  }

  return { text, masked: Array.from(maskedSet) };
}
