export type WrestlerMember = {
  ringName: string;
  realName?: string;
};

export type CompetitorInfo = {
  ringName: string;
  kind: "singles" | "tag" | "stable" | "group";
  kindLabel: string;
  members: WrestlerMember[];
};

type WrestlerEntry = {
  kind?: CompetitorInfo["kind"];
  members?: WrestlerMember[];
};

/** 링네임 → 팀/멤버 정보 (PLE 카드 로스터 기준) */
const WRESTLER_REGISTRY: Record<string, WrestlerEntry> = {
  "#DIY": {
    kind: "tag",
    members: [{ ringName: "Johnny Gargano" }, { ringName: "Tommaso Ciampa" }],
  },
  "The Wyatt Sicks": {
    kind: "stable",
    members: [
      { ringName: "Bo Dallas" },
      { ringName: "Dexter Lumis" },
      { ringName: "Joe Gacy" },
    ],
  },
  "Motor City Machine Guns": {
    kind: "tag",
    members: [{ ringName: "Alex Shelley" }, { ringName: "Chris Sabin" }],
  },
  Fraxiom: {
    kind: "tag",
    members: [{ ringName: "Nathan Frazer" }, { ringName: "Axiom" }],
  },
  "The Street Profits": {
    kind: "tag",
    members: [{ ringName: "Montez Ford" }, { ringName: "Angelo Dawkins" }],
  },
  "Andrade & Rey Fénix": {
    kind: "tag",
    members: [{ ringName: "Andrade" }, { ringName: "Rey Fénix" }],
  },
  "Alexa Bliss & Charlotte Flair": {
    kind: "tag",
    members: [{ ringName: "Alexa Bliss" }, { ringName: "Charlotte Flair" }],
  },
  "Raquel Rodriguez & Roxanne Perez": {
    kind: "tag",
    members: [{ ringName: "Raquel Rodriguez" }, { ringName: "Roxanne Perez" }],
  },
  "Roman Reigns & Jey Uso": {
    kind: "tag",
    members: [{ ringName: "Roman Reigns" }, { ringName: "Jey Uso" }],
  },
  "Bron Breakker & Bronson Reed": {
    kind: "tag",
    members: [{ ringName: "Bron Breakker" }, { ringName: "Bronson Reed" }],
  },
  "Drew McIntyre & Logan Paul": {
    kind: "tag",
    members: [{ ringName: "Drew McIntyre" }, { ringName: "Logan Paul" }],
  },
  "Randy Orton & Jelly Roll": {
    kind: "tag",
    members: [{ ringName: "Randy Orton" }, { ringName: "Jelly Roll" }],
  },
  "Paige & Brie Bella": {
    kind: "tag",
    members: [{ ringName: "Paige" }, { ringName: "Brie Bella" }],
  },
  "Nia Jax & Lash Legend": {
    kind: "tag",
    members: [{ ringName: "Nia Jax" }, { ringName: "Lash Legend" }],
  },
  "Bayley & Lyra Valkyria": {
    kind: "tag",
    members: [
      { ringName: "Bayley", realName: "Pamela Martinez" },
      { ringName: "Lyra Valkyria", realName: "Laura Weaver" },
    ],
  },
  "LA Knight & The Usos": {
    kind: "group",
    members: [
      { ringName: "LA Knight" },
      { ringName: "Jey Uso" },
      { ringName: "Jimmy Uso" },
    ],
  },
  "Rhodes & Jey Uso": {
    kind: "tag",
    members: [{ ringName: "Cody Rhodes" }, { ringName: "Jey Uso" }],
  },
  "Cena & Logan Paul": {
    kind: "tag",
    members: [{ ringName: "John Cena" }, { ringName: "Logan Paul" }],
  },
  "Danhausen & Minihausen": {
    kind: "tag",
    members: [{ ringName: "Danhausen" }, { ringName: "Minihausen" }],
  },
  "The Miz & Kit Wilson": {
    kind: "tag",
    members: [{ ringName: "The Miz" }, { ringName: "Kit Wilson" }],
  },
  "The Vanity Project": {
    kind: "tag",
    members: [{ ringName: "Carmelo Hayes" }, { ringName: "Andrade" }],
  },
  "Los Americanos": {
    kind: "tag",
    members: [{ ringName: "Angel" }, { ringName: "Berto" }],
  },
  BirthRight: {
    kind: "stable",
    members: [
      { ringName: "Arianna Grace" },
      { ringName: "Channing Lorenzo" },
      { ringName: "Lexis King" },
      { ringName: "Uriah Connors" },
      { ringName: "Charlie Dempsey" },
    ],
  },
  "Sinclair, Hank & Tank, EK Prosper, Shiloh Hill": {
    kind: "group",
    members: [
      { ringName: "Wren Sinclair" },
      { ringName: "Hank Walker" },
      { ringName: "Tank Ledger" },
      { ringName: "EK Prosper" },
      { ringName: "Shiloh Hill" },
    ],
  },
};

const KIND_LABEL: Record<CompetitorInfo["kind"], string> = {
  singles: "싱글",
  tag: "태그팀",
  stable: "스테이블",
  group: "팀",
};

function normalizeKey(name: string): string {
  return name.trim();
}

function lookupEntry(ringName: string): WrestlerEntry | undefined {
  const key = normalizeKey(ringName);
  return WRESTLER_REGISTRY[key];
}

function splitCompoundName(ringName: string): string[] | null {
  if (!ringName.includes(" & ")) return null;
  return ringName
    .split(" & ")
    .map((p) => p.trim())
    .filter(Boolean);
}

function buildFromMembers(
  ringName: string,
  members: WrestlerMember[],
  kind: CompetitorInfo["kind"],
): CompetitorInfo {
  return { ringName, kind, kindLabel: KIND_LABEL[kind], members };
}

/** 링네임으로 선수 프로필 정보를 조회한다. 미등록 시 링네임만 반환한다. */
export function resolveCompetitorInfo(ringName: string): CompetitorInfo {
  const key = normalizeKey(ringName);
  const direct = lookupEntry(key);
  if (direct) {
    if (direct.members?.length) {
      const kind =
        direct.kind ?? (direct.members.length > 2 ? "stable" : "tag");
      return buildFromMembers(key, direct.members, kind);
    }
  }

  const parts = splitCompoundName(key);
  if (parts && parts.length >= 2) {
    const members: WrestlerMember[] = parts.map((part) => ({ ringName: part }));
    return buildFromMembers(key, members, "tag");
  }

  return {
    ringName: key,
    kind: "singles",
    kindLabel: KIND_LABEL.singles,
    members: [],
  };
}
