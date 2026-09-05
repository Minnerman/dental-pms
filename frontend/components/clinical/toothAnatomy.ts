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
  roots: ["M32 102 C34 86 35 68 37 52 C39 35 40 23 44 15 C46 10 50 12 50 17 C49 27 51 37 54 50 C57 66 62 83 65 100 Q49 109 32 102 Z"],
  canals: ["M48 103 C47 83 46 64 45 47 C44 34 45 24 47 18"],
  grooves: [],
};

const upperLateral: ToothAnatomy = {
  crown: "M33 101 C42 94 56 95 65 102 C74 113 80 130 79 143 C80 153 76 160 68 163 C57 166 39 162 29 157 C21 152 19 145 22 134 C24 120 26 109 33 101 Z",
  roots: ["M33 105 C35 89 36 74 35 59 C34 44 31 32 33 22 C34 15 39 12 42 17 C44 22 42 29 44 36 C48 51 55 63 59 78 C62 88 64 97 66 104 Q50 112 33 105 Z"],
  canals: ["M49 106 C48 86 45 68 41 50 C38 36 37 25 38 20"],
  grooves: [],
};

const lowerIncisor: ToothAnatomy = {
  crown: "M31 104 C40 97 58 98 66 105 C71 115 75 134 75 152 C75 158 72 163 67 164 C56 162 44 165 32 162 C26 161 23 157 24 151 C25 134 25 115 31 104 Z",
  roots: ["M31 108 C34 89 36 71 38 55 C40 39 40 28 44 20 C46 15 50 14 52 18 C53 22 50 29 51 37 C52 60 60 88 66 108 Q47 116 31 108 Z"],
  canals: ["M47 109 C47 86 45 68 45 52 C45 37 47 27 48 22"],
  grooves: [],
};

const lowerLateral: ToothAnatomy = {
  ...lowerIncisor,
  roots: ["M31 108 C34 91 35 75 34 61 C33 45 31 34 34 25 C36 18 40 16 43 20 C45 24 42 31 44 40 C47 59 58 80 66 108 Q48 116 31 108 Z"],
  canals: ["M47 109 C47 87 44 69 40 50 C37 37 37 28 39 24"],
};

const canine: ToothAnatomy = {
  crown: "M31 100 C42 91 57 93 67 103 C75 113 79 127 78 138 C78 148 68 156 57 163 C53 168 48 168 43 164 C33 160 24 157 21 150 C17 142 21 125 23 115 C25 109 27 104 31 100 Z",
  roots: ["M31 104 C33 86 33 66 34 48 C35 31 36 17 40 9 C42 4 47 4 48 9 C49 16 45 23 47 32 C50 53 59 72 63 88 L67 104 Q49 113 31 104 Z"],
  canals: ["M48 106 C47 85 44 66 42 47 C40 32 41 18 43 11"],
  grooves: ["M49 114 C47 126 49 143 51 154"],
};

const lowerCanine: ToothAnatomy = {
  ...canine,
  roots: ["M31 104 C34 88 34 73 35 56 C36 40 35 27 39 16 C41 10 46 8 48 12 C50 17 46 26 48 36 C51 57 60 82 67 104 Q48 113 31 104 Z"],
  canals: ["M48 106 C47 84 44 65 42 47 C41 33 42 22 44 16"],
};

const upperPremolar: ToothAnatomy = {
  crown: "M27 100 C36 92 52 93 64 99 C74 103 80 116 81 129 C84 141 78 151 69 157 C63 161 57 162 51 157 C47 157 43 164 36 162 C24 159 18 153 17 144 C16 132 19 110 27 100 Z",
  roots: [
    "M27 104 C28 86 25 72 23 58 C21 44 18 32 20 25 C21 20 25 19 28 24 C33 33 34 46 38 58 C42 70 47 77 49 89 L50 105 Q39 110 27 104 Z",
    "M44 104 C46 90 47 77 48 65 C49 51 52 41 58 32 C61 26 66 23 68 27 C70 30 65 37 63 43 C59 57 62 78 65 103 Q54 111 44 104 Z",
  ],
  canals: ["M37 105 C37 86 31 69 28 52 C25 41 24 31 24 27", "M55 105 C54 85 53 70 55 57 C57 46 61 35 65 29"],
  grooves: ["M52 139 C50 147 50 153 51 157"],
};

const upperSecondPremolar: ToothAnatomy = {
  ...upperPremolar,
  crown: "M27 101 C40 93 55 96 67 102 C76 111 82 129 80 142 C79 151 72 158 62 161 C55 164 49 157 44 160 C38 164 29 160 24 155 C16 147 18 129 20 118 C21 109 23 105 27 101 Z",
  roots: ["M27 105 C30 88 31 73 31 58 C30 43 28 33 31 25 C33 19 37 17 41 21 C44 26 42 34 45 43 C48 57 57 69 61 84 L67 104 Q48 113 27 105 Z"],
  canals: ["M46 107 C45 88 42 70 38 52 C35 39 34 29 36 24"],
};

const lowerPremolar: ToothAnatomy = {
  crown: "M27 103 C37 96 55 95 66 102 C77 109 80 126 79 140 C77 151 69 156 59 160 C54 164 48 167 41 163 C31 161 20 156 19 146 C17 133 20 112 27 103 Z",
  roots: ["M27 107 C31 88 32 73 34 58 C35 43 34 32 38 24 C41 18 45 18 47 22 C49 27 45 35 47 44 C50 65 59 88 66 107 Q47 116 27 107 Z"],
  canals: ["M47 110 C45 89 43 72 41 57 C40 43 41 32 43 26"],
  grooves: ["M48 141 C47 150 47 157 48 164"],
};

const lowerSecondPremolar: ToothAnatomy = {
  ...lowerPremolar,
  roots: ["M27 107 C31 90 32 75 32 61 C31 47 28 37 31 29 C33 23 37 22 40 26 C43 30 41 36 44 46 C49 63 59 86 66 107 Q47 116 27 107 Z"],
  canals: ["M47 110 C45 91 42 74 38 57 C34 43 34 33 36 29"],
};

// Unequal, curved, overlapping roots form a cervical trunk instead of three spikes.
const upperMolar: ToothAnatomy = {
  crown: "M18 100 C28 93 37 98 48 96 C59 94 71 94 81 101 C88 108 89 122 92 136 C95 149 89 161 79 162 C73 163 66 157 61 154 C57 161 52 166 45 165 C37 165 35 158 31 156 C26 164 17 164 12 157 C6 149 8 134 9 122 C10 111 10 106 18 100 Z",
  roots: [
    "M33 105 C34 87 36 72 37 57 C38 39 36 24 40 15 C42 9 46 8 49 12 C52 17 49 27 50 37 C52 60 59 80 66 105 Z",
    "M18 104 C19 87 15 72 13 57 C11 43 7 31 10 26 C12 21 16 22 19 28 C23 38 25 49 29 60 C34 74 42 86 46 105 Q32 110 18 104 Z",
    "M55 104 C61 87 62 74 65 60 C68 46 73 34 80 29 C84 26 88 27 87 32 C86 38 80 44 78 53 C75 68 77 85 81 103 Q69 111 55 104 Z",
  ],
  canals: ["M49 105 C46 84 44 66 44 47 C44 34 43 23 45 16", "M31 106 C29 86 22 66 18 48 C15 39 13 31 14 28", "M69 106 C68 85 69 69 72 55 C75 44 80 35 83 32"],
  grooves: ["M31 133 C32 142 34 149 31 156", "M64 128 C62 139 59 147 61 154"],
};

// Second and third molars remain the same chart slots and crown outlines. Only
// the schematic root spread, curvature and length vary; no root finding is inferred.
const upperSecondMolar: ToothAnatomy = {
  ...upperMolar,
  roots: [
    "M33 105 C35 87 37 74 38 60 C39 45 37 32 40 23 C42 17 46 15 49 19 C51 24 48 32 50 42 C53 63 60 85 66 105 Z",
    "M18 104 C20 89 19 76 17 63 C15 50 11 39 14 32 C16 27 20 28 23 34 C26 41 27 52 31 63 C36 77 42 91 46 105 Q32 111 18 104 Z",
    "M55 104 C60 91 62 78 64 66 C66 54 69 44 75 36 C78 31 82 29 84 33 C86 38 80 43 78 51 C74 68 78 89 81 103 Q68 111 55 104 Z",
  ],
  canals: ["M49 105 C47 85 44 68 44 53 C44 39 43 29 45 22", "M31 106 C29 87 24 69 21 55 C19 45 18 37 19 34", "M69 106 C68 88 69 73 72 60 C75 46 79 38 80 36"],
};

const upperThirdMolar: ToothAnatomy = {
  ...upperMolar,
  roots: [
    "M33 105 C34 90 35 77 35 66 C34 52 31 42 34 33 C36 26 40 23 43 28 C46 33 43 39 45 48 C49 68 59 88 66 105 Z",
    "M18 104 C20 90 19 79 17 68 C15 56 11 47 14 41 C16 36 20 36 23 42 C26 49 26 57 30 67 C35 80 41 93 46 105 Q32 111 18 104 Z",
    "M55 104 C58 92 60 81 61 71 C62 59 63 49 68 42 C71 37 76 35 78 39 C80 44 75 49 74 57 C72 72 78 91 81 103 Q69 111 55 104 Z",
  ],
  canals: ["M49 105 C46 87 42 72 40 59 C37 47 37 37 39 32", "M31 106 C29 89 23 74 20 60 C18 52 17 45 18 42", "M69 106 C67 91 66 78 67 66 C68 54 71 45 74 41"],
};

const lowerMolar: ToothAnatomy = {
  crown: "M16 102 C29 95 39 100 50 98 C63 94 76 97 84 105 C91 114 94 133 91 147 C90 158 82 164 73 161 C67 158 64 157 60 161 C53 168 44 168 37 162 C34 158 30 157 27 160 C18 165 10 157 9 147 C6 135 8 111 16 102 Z",
  roots: [
    "M16 107 C20 91 21 77 19 62 C17 47 12 36 15 29 C17 24 21 24 24 30 C28 39 29 49 33 60 C38 73 43 79 44 92 L49 109 Q31 115 16 107 Z",
    "M49 108 C59 91 62 77 64 63 C66 49 66 38 72 29 C75 23 80 23 82 27 C84 32 78 39 76 48 C72 65 79 89 84 108 Q66 116 49 108 Z",
  ],
  canals: ["M31 108 C31 89 27 71 23 54 C20 43 18 34 20 30", "M67 109 C67 89 68 72 70 58 C71 43 75 33 78 29"],
  grooves: ["M28 134 C31 145 31 151 27 160", "M61 134 C62 147 57 153 60 161"],
};

const lowerSecondMolar: ToothAnatomy = {
  ...lowerMolar,
  roots: [
    "M16 107 C20 93 22 80 21 68 C20 54 17 45 19 38 C21 32 25 32 28 37 C31 44 30 52 34 63 C39 77 44 91 49 109 Q31 115 16 107 Z",
    "M49 108 C57 94 60 82 61 70 C63 56 63 46 68 37 C71 31 75 29 78 33 C80 38 75 43 74 52 C71 68 79 92 84 108 Q66 116 49 108 Z",
  ],
  canals: ["M31 108 C31 91 28 77 25 62 C23 50 22 42 24 38", "M67 109 C65 92 65 79 67 66 C68 53 71 42 74 36"],
};

const lowerThirdMolar: ToothAnatomy = {
  ...lowerMolar,
  roots: [
    "M16 107 C20 94 22 83 21 73 C20 62 17 54 19 48 C21 42 25 41 28 45 C31 50 29 57 33 67 C38 82 44 96 49 109 Q31 115 16 107 Z",
    "M49 108 C56 96 59 87 60 77 C61 64 60 55 64 48 C67 42 71 40 74 44 C76 49 72 54 71 61 C70 77 79 95 84 108 Q66 116 49 108 Z",
  ],
  canals: ["M31 108 C30 93 27 81 25 69 C22 58 23 50 24 47", "M67 109 C64 96 63 84 64 73 C65 62 67 53 70 47"],
};

// Primary teeth use the same permanent-position slots only when the operator
// explicitly records deciduous dentition. Positions 4/5 are primary molars,
// not scaled permanent premolars. These remain schematic illustrations.
const deciduousIncisor: ToothAnatomy = {
  crown: "M31 109 C38 103 56 102 65 108 C74 115 80 127 80 139 C80 146 76 152 68 153 C54 155 40 155 29 151 C22 149 19 143 20 136 C21 124 24 115 31 109 Z",
  roots: ["M31 111 C34 96 35 82 36 70 C37 57 37 47 40 41 C42 36 46 35 48 39 C50 43 47 49 49 57 C52 74 60 97 65 111 Q48 119 31 111 Z"],
  canals: ["M47 113 C46 95 43 79 43 67 C42 54 43 45 44 41"],
  grooves: [],
};

const deciduousCanine: ToothAnatomy = {
  crown: "M31 109 C42 101 57 103 66 110 C75 118 81 131 78 141 C75 149 64 152 56 159 C52 163 48 162 44 158 C35 154 24 152 21 143 C18 135 23 118 31 109 Z",
  roots: ["M31 111 C34 95 34 81 35 66 C36 49 35 36 39 28 C41 23 45 22 47 26 C49 31 45 37 47 47 C50 68 59 93 66 112 Q48 120 31 111 Z"],
  canals: ["M47 114 C46 94 44 77 42 62 C41 48 41 36 43 29"],
  grooves: ["M49 121 C48 134 49 144 51 153"],
};

const deciduousUpperMolar: ToothAnatomy = {
  crown: "M22 107 C30 101 40 105 49 104 C60 102 70 103 78 109 C87 117 94 131 90 143 C87 151 81 156 74 152 C67 148 64 148 59 153 C52 159 46 158 40 152 C35 148 31 150 27 153 C19 157 11 151 10 143 C7 130 13 115 22 107 Z",
  roots: [
    "M37 112 C38 95 40 78 40 64 C40 51 38 40 41 33 C43 27 47 25 50 29 C52 34 49 41 50 49 C52 70 57 94 63 112 Z",
    "M22 111 C22 96 18 83 13 69 C9 57 5 49 8 44 C10 40 14 40 17 45 C21 53 24 65 29 78 C34 91 38 101 40 114 Z",
    "M59 112 C64 97 69 82 74 68 C78 56 82 47 87 44 C91 41 94 44 92 49 C89 56 86 63 84 72 C79 88 78 101 78 112 Q69 120 59 112 Z",
  ],
  canals: ["M49 114 C47 96 46 79 46 65 C45 52 44 40 46 32", "M31 114 C27 94 20 73 15 59 C12 51 11 47 12 45", "M69 114 C71 97 77 77 82 63 C85 55 88 49 89 47"],
  grooves: ["M30 132 Q34 143 27 153", "M63 131 Q59 141 59 153"],
};

const deciduousLowerMolar: ToothAnatomy = {
  ...deciduousUpperMolar,
  roots: [
    "M22 111 C22 95 18 81 13 67 C9 56 5 47 8 42 C10 37 14 37 17 43 C21 51 24 63 29 77 C35 92 41 105 43 114 Z",
    "M55 113 C62 97 68 81 73 66 C77 54 82 44 87 40 C91 37 94 40 92 45 C89 53 85 61 83 71 C79 88 78 103 78 113 Q67 120 55 113 Z",
  ],
  canals: ["M32 114 C28 95 21 75 16 60 C12 50 11 44 12 42", "M68 115 C72 97 77 77 82 62 C85 52 88 45 89 43"],
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
  if (position <= 2) return upper ? (position === 1 ? upperCentral : upperLateral) : (position === 1 ? lowerIncisor : lowerLateral);
  if (position === 3) return upper ? canine : lowerCanine;
  if (position <= 5) return upper ? (position === 4 ? upperPremolar : upperSecondPremolar) : (position === 4 ? lowerPremolar : lowerSecondPremolar);
  if (position === 7) return upper ? upperSecondMolar : lowerSecondMolar;
  if (position === 8) return upper ? upperThirdMolar : lowerThirdMolar;
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
