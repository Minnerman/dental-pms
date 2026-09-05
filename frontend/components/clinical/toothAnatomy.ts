/** Original R4-inspired tooth silhouettes, drawn in a 100 × 170 box.
 * These are schematic illustrations, not patient-specific root/anatomy findings.
 * Roots point up here; the renderer reflects the lower arch toward the surface map.
 * Crown and root paths stay separate so clinical overlays remain independent.
 */
type ToothAnatomy = {
  crown: string;
  roots: string[];
  canals: string[];
  grooves: string[];
};

// A schematic implant fixture, not a brand, measured size or treatment entry.
// The apical tip is narrower than the cervical end beside the crown. Raised
// oblique threads distinguish the screw from a natural root or a perforated post.
export const implantScrewAnatomy = {
  body: "M45 17 Q50 12 55 17 C60 27 64 53 68 84 L68 95 H32 L32 84 C36 53 40 27 45 17 Z",
  collar: "M31 94 Q50 91 69 94 L65 105 H35 Z",
  threads: [28, 37, 46, 55, 64, 73, 82].map((y) => {
    const halfWidth = 11 + (y - 28) / 6;
    const left = 50 - halfWidth;
    const right = 50 + halfWidth;
    return `M${left} ${y + 3} L${right} ${y - 1} L${right + 1} ${y + 2} L${left + 1} ${y + 6} Z`;
  }),
};

const upperCentral: ToothAnatomy = {
  crown: "M32 99 C41 92 56 91 65 97 C74 104 80 119 82 136 C84 146 80 155 72 160 C61 165 43 164 32 159 C22 155 17 149 18 139 C19 122 23 107 32 99 Z",
  roots: ["M32 102 C34 84 34 67 38 49 C41 32 46 18 50 13 C53 9 58 11 58 17 C56 29 58 40 60 52 C62 70 64 86 65 100 C55 106 43 108 32 102 Z"],
  canals: ["M48 103 C48 79 47 58 50 39 Q53 26 54 18"],
  grooves: [],
};

const upperLateral: ToothAnatomy = {
  crown: "M33 101 C42 94 56 95 65 102 C74 113 80 130 79 143 C80 153 76 160 68 163 C57 166 39 162 29 157 C21 152 19 145 22 134 C24 120 26 109 33 101 Z",
  roots: ["M33 105 C36 79 38 57 39 38 C39 25 42 14 47 13 C52 12 55 19 55 28 C57 42 62 49 64 67 L66 104 Q50 111 33 105 Z"],
  canals: ["M49 106 C50 77 49 53 47 23"],
  grooves: [],
};

const lowerIncisor: ToothAnatomy = {
  crown: "M31 104 C40 97 58 98 66 105 C71 115 75 134 75 152 C75 158 72 163 67 164 C56 162 44 165 32 162 C26 161 23 157 24 151 C25 134 25 115 31 104 Z",
  roots: ["M31 108 C34 85 36 64 40 44 C42 29 46 16 50 15 C55 15 54 24 54 31 C53 52 60 77 66 108 Q47 114 31 108 Z"],
  canals: ["M47 109 C47 74 49 42 50 23"],
  grooves: [],
};

const canine: ToothAnatomy = {
  crown: "M31 100 C42 91 57 93 67 103 C75 113 79 127 78 138 C78 148 68 156 57 163 C53 168 48 168 43 164 C33 160 24 157 21 150 C17 142 21 125 23 115 C25 109 27 104 31 100 Z",
  roots: ["M31 104 C33 87 32 68 36 46 C39 27 43 10 49 6 C54 3 56 7 55 12 C52 29 58 43 60 58 C63 74 66 91 67 104 Q49 112 31 104 Z"],
  canals: ["M48 106 C47 78 46 54 49 29 L51 12"],
  grooves: ["M49 114 C47 126 49 143 51 154"],
};

const upperPremolar: ToothAnatomy = {
  crown: "M27 100 C36 92 52 93 64 99 C74 103 80 116 81 129 C84 141 78 151 69 157 C63 161 57 162 51 157 C47 157 43 164 36 162 C24 159 18 153 17 144 C16 132 19 110 27 100 Z",
  roots: [
    "M27 104 C28 85 21 68 23 49 C22 35 21 22 26 19 C31 18 35 27 37 34 C41 48 47 61 48 77 L50 105 Z",
    "M45 103 C49 82 47 65 52 48 C56 31 65 22 69 23 C73 24 69 31 66 37 C61 53 66 80 65 103 Q55 110 45 103 Z",
  ],
  canals: ["M36 104 C37 80 31 61 28 28", "M56 105 C55 75 56 49 65 29"],
  grooves: ["M52 139 C50 147 50 153 51 157"],
};

const upperSecondPremolar: ToothAnatomy = {
  ...upperPremolar,
  crown: "M27 101 C40 93 55 96 67 102 C76 111 82 129 80 142 C79 151 72 158 62 161 C55 164 49 157 44 160 C38 164 29 160 24 155 C16 147 18 129 20 118 C21 109 23 105 27 101 Z",
  roots: ["M27 105 C30 82 32 70 32 53 C33 38 30 28 34 22 C39 16 44 23 48 27 C49 42 58 49 61 65 C64 78 65 92 67 104 Q48 112 27 105 Z"],
  canals: ["M46 107 C47 85 42 65 42 48 Q40 35 38 26"],
};

const lowerPremolar: ToothAnatomy = {
  crown: "M27 103 C37 96 55 95 66 102 C77 109 80 126 79 140 C77 151 69 156 59 160 C54 164 48 167 41 163 C31 161 20 156 19 146 C17 133 20 112 27 103 Z",
  roots: ["M27 107 C30 84 33 62 40 40 C44 26 49 20 53 21 C58 22 54 31 54 40 C53 57 62 82 66 107 Q47 114 27 107 Z"],
  canals: ["M47 110 C44 79 49 48 51 28"],
  grooves: ["M48 141 C47 150 47 157 48 164"],
};

// Unequal, curved, overlapping roots form a cervical trunk instead of three spikes.
const upperMolar: ToothAnatomy = {
  crown: "M18 100 C28 93 37 98 48 96 C59 94 71 94 81 101 C88 108 89 122 92 136 C95 149 89 161 79 162 C73 163 66 157 61 154 C57 161 52 166 45 165 C37 165 35 158 31 156 C26 164 17 164 12 157 C6 149 8 134 9 122 C10 111 10 106 18 100 Z",
  roots: [
    "M34 105 C33 88 36 75 37 57 C39 36 41 12 47 9 C53 7 55 18 54 27 C54 57 65 80 66 105 Z",
    "M18 104 C19 84 16 67 14 51 C11 40 7 27 11 24 C15 21 21 28 26 34 C35 44 34 64 39 77 C43 87 45 96 46 105 Z",
    "M55 104 C63 83 62 68 68 54 C74 42 81 27 87 26 C93 26 89 36 86 43 C78 62 79 85 81 103 Q69 111 55 104 Z",
  ],
  canals: ["M49 105 Q46 64 49 18", "M31 106 C29 79 23 48 14 31", "M69 106 Q71 64 85 33"],
  grooves: ["M31 133 C32 142 34 149 31 156", "M64 128 C62 139 59 147 61 154"],
};

const lowerMolar: ToothAnatomy = {
  crown: "M16 102 C29 95 39 100 50 98 C63 94 76 97 84 105 C91 114 94 133 91 147 C90 158 82 164 73 161 C67 158 64 157 60 161 C53 168 44 168 37 162 C34 158 30 157 27 160 C18 165 10 157 9 147 C6 135 8 111 16 102 Z",
  roots: [
    "M16 107 C20 87 22 70 18 53 C14 39 12 28 17 25 C22 22 28 35 32 42 C39 55 42 66 43 79 L49 109 Z",
    "M49 108 C61 86 65 68 67 51 C70 35 76 23 81 25 C86 27 80 40 79 48 C75 65 80 85 84 108 Q67 115 49 108 Z",
  ],
  canals: ["M31 108 C31 81 25 51 19 32", "M67 109 C69 83 72 53 79 32"],
  grooves: ["M28 134 C31 145 31 151 27 160", "M61 134 C62 147 57 153 60 161"],
};

// Primary teeth use the same permanent-position slots only when the operator
// explicitly records deciduous dentition. Positions 4/5 are primary molars,
// not scaled permanent premolars. These remain schematic illustrations.
const deciduousIncisor: ToothAnatomy = {
  crown: "M31 109 C38 103 56 102 65 108 C74 115 80 127 80 139 C80 146 76 152 68 153 C54 155 40 155 29 151 C22 149 19 143 20 136 C21 124 24 115 31 109 Z",
  roots: ["M31 111 C34 94 36 78 39 64 C41 50 45 38 50 35 C54 33 56 38 55 44 C53 61 59 88 65 111 Q48 118 31 111 Z"],
  canals: ["M47 113 C47 88 49 61 51 42"],
  grooves: [],
};

const deciduousCanine: ToothAnatomy = {
  crown: "M31 109 C42 101 57 103 66 110 C75 118 81 131 78 141 C75 149 64 152 56 159 C52 163 48 162 44 158 C35 154 24 152 21 143 C18 135 23 118 31 109 Z",
  roots: ["M31 111 C34 94 33 80 36 64 C39 45 44 25 50 23 C55 21 56 26 54 32 C53 52 61 79 66 112 Q48 119 31 111 Z"],
  canals: ["M47 114 C47 85 47 55 51 31"],
  grooves: ["M49 121 C48 134 49 144 51 153"],
};

const deciduousUpperMolar: ToothAnatomy = {
  crown: "M22 107 C30 101 40 105 49 104 C60 102 70 103 78 109 C87 117 94 131 90 143 C87 151 81 156 74 152 C67 148 64 148 59 153 C52 159 46 158 40 152 C35 148 31 150 27 153 C19 157 11 151 10 143 C7 130 13 115 22 107 Z",
  roots: [
    "M37 112 C38 93 39 76 42 58 C43 44 46 28 51 26 C55 25 57 32 55 38 C53 57 57 82 63 112 Z",
    "M22 111 C23 95 18 81 13 66 C8 51 6 42 10 40 C14 38 20 50 24 57 C32 74 38 92 40 114 Z",
    "M59 112 C64 94 71 76 76 62 C80 49 87 38 91 41 C94 44 87 60 85 70 C80 87 78 99 78 112 Q69 118 59 112 Z",
  ],
  canals: ["M49 114 Q47 75 51 34", "M31 114 C27 89 18 60 12 46", "M69 114 C71 90 81 63 88 47"],
  grooves: ["M30 132 Q34 143 27 153", "M63 131 Q59 141 59 153"],
};

const deciduousLowerMolar: ToothAnatomy = {
  ...deciduousUpperMolar,
  roots: [
    "M22 111 C23 92 19 77 13 60 C9 49 6 40 10 38 C15 36 21 49 27 61 C36 79 42 95 43 114 Z",
    "M55 113 C63 94 68 78 75 61 C81 46 88 34 92 39 C95 44 86 58 83 73 C79 89 78 102 78 113 Q67 119 55 113 Z",
  ],
  canals: ["M32 114 C30 91 18 59 12 44", "M68 115 C72 91 83 58 90 44"],
};

export function getToothAnatomy(
  toothKey: string,
  dentition: "permanent" | "deciduous" = "permanent"
): ToothAnatomy {
  const upper = toothKey.startsWith("U");
  const position = Number(toothKey.slice(-1));
  if (dentition === "deciduous" && position >= 1 && position <= 5) {
    if (position <= 2) return deciduousIncisor;
    if (position === 3) return deciduousCanine;
    return upper ? deciduousUpperMolar : deciduousLowerMolar;
  }
  if (position <= 2) return upper ? (position === 1 ? upperCentral : upperLateral) : lowerIncisor;
  if (position === 3) return canine;
  if (position <= 5) return upper ? (position === 4 ? upperPremolar : upperSecondPremolar) : lowerPremolar;
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
