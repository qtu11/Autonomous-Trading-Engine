"use client";

interface CountryFlagProps {
  currency: string;
}

const flags: Record<string, string> = {
  USD: "🇺🇸", EUR: "🇪🇺", JPY: "🇯🇵", GBP: "🇬🇧", CHF: "🇨🇭",
  AUD: "🇦🇺", NZD: "🇳🇿", CAD: "🇨🇦", CNY: "🇨🇳", INR: "🇮🇳",
  BRL: "🇧🇷", MXN: "🇲🇽", ZAR: "🇿🇦", KRW: "🇰🇷", SGD: "🇸🇬",
  HKD: "🇭🇰", TWD: "🇹🇼", THB: "🇹🇭", MYR: "🇲🇾", IDR: "🇮🇩",
  PHP: "🇵🇭", VND: "🇻🇳", TRY: "🇹🇷", RUB: "🇷🇺", PLN: "🇵🇱",
  SEK: "🇸🇪", NOK: "🇳🇴", DKK: "🇩🇰", CZK: "🇨🇿", HUF: "🇭🇺",
  ILS: "🇮🇱", SAR: "🇸🇦", AED: "🇦🇪", QAR: "🇶🇦", KWD: "🇰🇼",
};

export default function CountryFlag({ currency }: CountryFlagProps) {
  const flag = flags[currency] || "🌐";
  return (
    <span style={{ fontSize: "14px", lineHeight: 1, display: "inline-flex", alignItems: "center" }}>
      {flag}
    </span>
  );
}