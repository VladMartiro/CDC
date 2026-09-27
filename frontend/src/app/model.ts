/*
  Runs the exported gradient-boosting models (public/model.json, written by
  analyses/export_model.py) directly in the browser. Each model is 400 decision
  trees; a prediction walks every tree to a leaf, sums the leaf values and applies
  the logistic function, exactly like scikit-learn's HistGradientBoostingClassifier.
*/

export interface Tree {
  feature: number[];
  threshold: number[];
  missing_left: number[];
  left: number[];
  right: number[];
  value: number[];
  categorical: number[];
  bitset: number[];
  bitsets: number[][];
}

export interface FairnessRow {
  attribute: string;
  group: string;
  n: number;
  predicted: number;
  actual: number;
  auc: number | null;
}

export interface OutcomeModel {
  baseline: number;
  known: Record<string, number[]>;
  trees: Tree[];
  national_rate: number;
  auc: number;
  fairness: FairnessRow[];
}

export interface ModelFile {
  features: string[];
  numeric: string[];
  categories: Record<string, string[]>;
  outcomes: Record<string, OutcomeModel>;
}

export type Inputs = Record<string, string | number>;

function hasBit(bitset: number[], value: number): boolean {
  return ((bitset[value >> 5] >>> (value & 31)) & 1) === 1;
}

/* Turn named inputs into the numeric row the trees expect (category -> index). */
export function encode(model: ModelFile, inputs: Inputs): number[] {
  return model.features.map(feature => {
    const value = inputs[feature];

    if (model.numeric.includes(feature)) {
      return Number(value);
    }

    const index = model.categories[feature].indexOf(String(value));
    return index < 0 ? NaN : index;
  });
}

/* Probability (0 to 1) of one outcome for one encoded row. */
export function predict(outcome: OutcomeModel, row: number[]): number {
  let raw = outcome.baseline;

  for (const tree of outcome.trees) {
    let node = 0;

    while (tree.left[node] !== -1) {
      const feature = tree.feature[node];
      const value = row[feature];
      let goLeft: boolean;

      if (Number.isNaN(value)) {
        goLeft = tree.missing_left[node] === 1;
      } else if (tree.categorical[node] === 1) {
        const known = outcome.known[feature];
        goLeft = known && hasBit(known, value)
          ? hasBit(tree.bitsets[tree.bitset[node]], value)
          : tree.missing_left[node] === 1;
      } else {
        goLeft = value <= tree.threshold[node];
      }

      node = goLeft ? tree.left[node] : tree.right[node];
    }

    raw += tree.value[node];
  }

  return 1 / (1 + Math.exp(-raw));
}
