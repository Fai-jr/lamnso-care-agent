import Link from "next/link";

// -------------------------------------------------------------
// Verified Cameroon emergency numbers — confirmed across multiple
// independent sources (national police site, embassy advisories).
// Worth knowing: outside major towns, dispatched ambulance response
// can be unreliable — see the note rendered below this list.
// -------------------------------------------------------------
const EMERGENCY_NUMBERS = [
  { label: "Police", number: "117" },
  { label: "Fire", number: "118" },
  { label: "Ambulance", number: "119" },
];

// -------------------------------------------------------------
// The two confirmed major hospitals serving Bui Division, both in
// Kumbo. Names and locations are verified. Phone numbers are NOT
// filled in on purpose — a wrong number shown to someone in crisis
// is worse than no number. Confirm directly with each hospital and
// fill these in before this page goes in front of real users.
// -------------------------------------------------------------
const HOSPITALS = [
  {
    name: "Banso Baptist Hospital",
    location: "Kumbo, Bui Division",
    phone: null, // TODO: confirm and add verified phone number
  },
  {
    name: "St. Elizabeth Catholic General Hospital (Shisong)",
    location: "Kumbo, Bui Division",
    phone: null, // TODO: confirm and add verified phone number
  },
];

export default function HelpPage() {
  return (
    <div className="flex min-h-screen flex-col bg-[#F7F1E8]">
      {/* Header — mirrors the chat page for continuity */}
      <header className="border-b border-[#D8C9AE] bg-[#3A2E26] px-6 py-5 sm:px-10">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <div>
            <h1 className="font-serif text-2xl tracking-tight text-[#F7F1E8]">
              Get help
            </h1>
            <p className="mt-0.5 text-sm text-[#C9B79C]">
              If things feel like too much right now, here&rsquo;s how to reach a person directly.
            </p>
          </div>
          <Link
            href="/"
            className="rounded-full bg-[#4A3B30] px-4 py-2 text-sm text-[#E8DCC8] transition-colors hover:bg-[#5A4A3C]"
          >
            ← Back to chat
          </Link>
        </div>
      </header>

      <main className="flex flex-1 justify-center px-4 py-8 sm:px-6">
        <div className="flex w-full max-w-3xl flex-col gap-8">
          {/* Most urgent — placed first on purpose */}
          <section>
            <h2 className="font-serif text-xl text-[#3A2E26]">
              If you&rsquo;re in danger right now
            </h2>
            <p className="mt-2 text-[15px] leading-relaxed text-[#5C4A38]">
              Please don&rsquo;t wait on this — reach out immediately to someone you trust, or use one of the contacts below.
            </p>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {EMERGENCY_NUMBERS.map((item) => (
                <div
                  key={item.label}
                  className="rounded-xl border-l-4 border-[#8C6D4F] bg-white/70 px-4 py-3"
                >
                  <p className="text-xs uppercase tracking-wide text-[#A99A82]">
                    {item.label}
                  </p>
                  <p className="mt-1 text-2xl font-medium text-[#3A2E26]">
                    {item.number}
                  </p>
                </div>
              ))}
            </div>

            <p className="mt-3 text-sm leading-relaxed text-[#8A7A63]">
              Outside major towns, calling for an ambulance isn&rsquo;t always reliable. If you&rsquo;re able to, going straight to the nearest hospital — or asking someone nearby to take you — is often faster.
            </p>
          </section>

          {/* Local hospitals */}
          <section>
            <h2 className="font-serif text-xl text-[#3A2E26]">
              Hospitals in Bui Division
            </h2>
            <div className="mt-4 space-y-3">
              {HOSPITALS.map((hospital) => (
                <div
                  key={hospital.name}
                  className="rounded-xl border border-[#E2D4BC] bg-white/70 px-4 py-3"
                >
                  <p className="font-medium text-[#3A2E26]">{hospital.name}</p>
                  <p className="text-sm text-[#8A7A63]">{hospital.location}</p>
                  <p className="mt-1 text-sm italic text-[#A99A82]">
                    {hospital.phone
                      ? `Phone: ${hospital.phone}`
                      : "Phone number to be confirmed — visit in person for now."}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* Softer, community-rooted option */}
          <section>
            <h2 className="font-serif text-xl text-[#3A2E26]">
              Talk to someone close to you
            </h2>
            <p className="mt-2 text-[15px] leading-relaxed text-[#5C4A38]">
              A trusted family member, friend, or a community or church leader can also help right now — you don&rsquo;t have to carry this alone.
            </p>
          </section>

          <p className="mt-2 text-center text-xs text-[#A99A82]">
            Muna is here to listen, but it isn&rsquo;t a substitute for a doctor or a person who can be there with you in person.
          </p>

          <div className="flex justify-center pb-4">
            <Link
              href="/"
              className="rounded-xl bg-[#8C6D4F] px-5 py-3 font-medium text-white transition-colors hover:bg-[#74573D]"
            >
              Back to chat
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
