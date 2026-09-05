/** Presentation-only adult tooth silhouettes, drawn in a 100 × 170 box.
 * These are schematic shapes, not patient-specific root/anatomy findings.
 * Roots point up here; the renderer reflects the lower arch toward the surface map.
 */
type ToothAnatomy = {
  crown: string;
  roots: string[];
  canals: string[];
  grooves: string[];
};

const incisor: ToothAnatomy = {
  crown: "M29 103 Q48 95 68 103 C74 114 79 143 77 159 Q76 164 69 164 L29 164 Q22 164 22 158 C22 142 24 115 29 103 Z",
  roots: ["M29 106 C32 79 37 35 49 13 Q53 6 55 14 C54 43 64 74 68 106 Q48 113 29 106 Z"],
  canals: ["M49 108 C48 74 51 43 53 19"],
  grooves: [],
};

const canine: ToothAnatomy = {
  crown: "M29 103 Q49 95 68 103 C76 117 80 137 74 147 L54 166 Q51 169 47 166 L25 151 C18 146 21 120 29 103 Z",
  roots: ["M29 107 C34 80 37 30 48 7 Q52 1 55 8 C53 32 64 78 68 107 Q48 113 29 107 Z"],
  canals: ["M49 108 C48 72 51 34 52 13"],
  grooves: ["M49 112 Q53 132 51 151"],
};

const premolar: ToothAnatomy = {
  crown: "M24 103 Q49 95 74 103 C81 114 84 135 78 148 Q73 158 61 161 L51 157 Q44 156 38 161 C29 163 18 150 18 139 C17 126 19 111 24 103 Z",
  roots: [
    "M24 107 C26 82 22 48 30 21 Q33 13 37 23 C42 46 45 72 48 105 Z",
    "M48 105 C50 74 56 42 65 22 Q70 15 72 24 C66 49 71 82 74 107 Z",
  ],
  canals: ["M36 107 Q35 62 33 29", "M60 107 Q60 61 68 28"],
  grooves: ["M50 139 Q49 149 51 157"],
};

const singlePremolar: ToothAnatomy = {
  ...premolar,
  roots: ["M24 107 C29 77 35 39 48 19 Q55 11 56 22 C54 44 68 79 74 107 Q48 114 24 107 Z"],
  canals: ["M49 109 C47 75 51 42 52 24"],
};

const upperMolar: ToothAnatomy = {
  crown: "M13 103 Q28 95 43 99 Q57 95 85 103 C92 112 94 135 87 150 Q81 164 69 162 L58 157 Q52 155 46 161 Q36 168 28 159 Q13 164 9 148 C5 133 6 112 13 103 Z",
  roots: [
    "M13 108 C16 83 13 49 8 24 Q7 15 14 20 C29 31 35 59 37 82 L41 106 Z",
    "M34 106 C38 84 36 42 44 17 Q47 9 51 18 C61 43 58 83 63 107 Z",
    "M59 106 C67 84 68 45 84 24 Q91 16 91 24 C83 54 82 79 85 108 Z",
  ],
  canals: ["M25 107 C24 71 20 44 13 26", "M49 107 Q49 52 47 23", "M73 107 Q73 54 86 29"],
  grooves: ["M31 138 Q34 149 28 159", "M58 134 Q55 147 58 157"],
};

const lowerMolar: ToothAnatomy = {
  crown: "M13 103 Q31 96 48 100 Q68 96 85 103 C93 113 94 135 88 148 Q83 161 71 158 Q60 168 50 160 Q41 165 30 159 Q14 163 9 148 C5 132 6 114 13 103 Z",
  roots: [
    "M13 108 C21 80 18 46 20 23 Q22 14 27 22 C43 44 39 69 44 94 L46 108 Z",
    "M52 108 C62 85 62 51 75 24 Q80 16 82 25 C76 52 80 79 85 108 Z",
  ],
  canals: ["M28 109 C29 80 29 45 24 28", "M68 109 Q71 55 78 29"],
  grooves: ["M30 139 Q32 151 30 159", "M69 139 Q68 151 71 158"],
};

export function getToothAnatomy(toothKey: string): ToothAnatomy {
  const upper = toothKey.startsWith("U");
  const position = Number(toothKey.slice(-1));
  if (position <= 2) return incisor;
  if (position === 3) return canine;
  if (position <= 5) return upper && position === 4 ? premolar : singlePremolar;
  return upper ? upperMolar : lowerMolar;
}

/** Width variation distinguishes central/lateral incisors and second/third molars. */
export function getToothAnatomyWidth(toothKey: string): number {
  const upper = toothKey.startsWith("U");
  const position = Number(toothKey.slice(-1));
  if (position === 1) return upper ? 1 : 0.76;
  if (position === 2) return upper ? 0.85 : 0.82;
  if (position === 5) return 0.92;
  if (position === 7) return 0.94;
  if (position === 8) return 0.86;
  return 1;
}
