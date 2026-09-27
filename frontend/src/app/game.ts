/*
  Data-driven college game. Every decision maps to either
    (a) an input of our Census model (major, second major, where you search, grad school), or
    (b) a published effect size (internships, first-job persistence), or
    (c) a published fact with no measurable effect on the score (clearly labeled).

  Score = chance your first job after graduation needs your degree:
    P1 = (1 - P(unemployed)) x (1 - P(underemployed))
  with both probabilities from the model, averaged over the real mix of graduates
  (sex x race x born in US), so the score reflects choices, not identity.
  Long-run score = chance of a degree-level job 10 years out:
    P10 = P1 x 0.79 + (1 - P1) x 0.27        (Strada & Burning Glass Institute, 2024)
*/

import { encode, type ModelFile, predict } from './model';

export interface GameData {
  mix: { sex: string; race: string; born_us: string; share: number }[];
  states: Record<string, number>;
  second_majors: Record<string, number>;
  majors: Record<string, { unemployed: number; underemployed: number; ai_exposed_share: number | null }>;
}

export interface Choices {
  major?: string;
  aiClass?: 'challenge' | 'easy';
  secondMajor?: string;
  internship?: 'paid' | 'unpaid' | 'none';
  aiCert?: 'yes' | 'no';
  search?: 'home' | 'anywhere';
  grad?: 'yes' | 'no';
  offer?: 'accept' | 'keep';
}

export const HOME_STATE = 'North Carolina';

/* "Other" second major = average over the most common second majors (weighted by how often
   graduates pick them). Top 12 cover about 77% of second majors; weights are renormalized. */
export const ANY_SECOND_MAJOR = 'any';
const OTHER_TOP_N = 12;

/* Published numbers used by the game, each with its source. */
export const RESEARCH = {
  internshipOddsRatio: 0.51,     // odds of underemployment 49% lower with an internship (Strada & BGI 2024)
  internshipShare: 0.68,         // "more than two-thirds" of 2024 seniors had an internship (NACE 2024)
  stayCollegeLevel: 0.79,        // start in a college-level job -> still in one later (Strada & BGI 2024)
  leaveUnderemployment: 0.27,    // start underemployed -> 73% still underemployed 10 years later
};

export const SOURCES = [
  'Strada Education Foundation & Burning Glass Institute (2024). Talent Disrupted: College Graduates, Underemployment, and the Way Forward.',
  'National Association of Colleges and Employers (2024). The 2024 Student Survey Report: Four-Year Schools.',
  'National Association of Colleges and Employers (2025, 2026). Job Outlook.',
  'PwC (2025). The Fearless Future: 2025 Global AI Jobs Barometer.',
  'Brynjolfsson, E., Chandar, B., & Chen, R. (2025). Canaries in the Coal Mine? Six Facts about the Recent Employment Effects of Artificial Intelligence. Stanford Digital Economy Lab.',
  'Eloundou, T., Manning, S., Mishkin, P., & Rock, D. (2023). GPTs are GPTs: An Early Look at the Labor Market Impact Potential of Large Language Models.',
  'U.S. Census Bureau. American Community Survey 1-year PUMS, 2019 and 2021-2023 (our model).'
];

const odds = (p: number) => p / (1 - p);
const prob = (o: number) => o / (1 + o);

/* Model probabilities averaged over the graduate mix (and over states if searching anywhere). */
const cache = new Map<string, { unemployed: number; underemployed: number }>();

export function modelRates(model: ModelFile, data: GameData, c: Choices) {
  const key = JSON.stringify([c.major, c.secondMajor, c.search, c.grad]);
  const hit = cache.get(key);
  if (hit) {
    return hit;
  }

  const states: [string, number][] = c.search === 'anywhere'
    ? Object.entries(data.states)
    : [[HOME_STATE, 1]];

  const seconds: [string, number][] = c.secondMajor === ANY_SECOND_MAJOR
    ? Object.entries(data.second_majors).filter(([m]) => m !== c.major).slice(0, OTHER_TOP_N)
    : [[c.secondMajor ?? 'None', 1]];
  const secondTotal = seconds.reduce((sum, [, w]) => sum + w, 0);

  let unemployed = 0;
  let underemployed = 0;

  for (const person of data.mix) {
    for (const [state, stateShare] of states) {
     for (const [second, secondShare] of seconds) {
      const row = encode(model, {
        major: c.major ?? 'Business',
        second_major: second,
        sex: person.sex,
        race: person.race,
        born_us: person.born_us,
        state,
        moved_states: c.search === 'anywhere' && state !== HOME_STATE && person.born_us === 'Yes' ? 'Yes' : 'No',
        grad_degree: c.grad === 'yes' ? 'Yes' : 'No',
        year: '2023',
        age: 24
      });
      const w = person.share * stateShare * secondShare / secondTotal;
      unemployed += w * predict(model.outcomes['unemployed'], row);
      underemployed += w * predict(model.outcomes['underemployed'], row);
     }
    }
  }

  const total = data.mix.reduce((sum, p) => sum + p.share, 0);
  const result = { unemployed: unemployed / total, underemployed: underemployed / total };
  cache.set(key, result);
  return result;
}

/* The model's rates are averages over graduates with and without internships;
   split them using the published odds ratio. */
export function withInternship(underemployed: number, internship?: Choices['internship']): number {
  if (!internship) {
    return underemployed;
  }
  const { internshipOddsRatio: or, internshipShare: q } = RESEARCH;
  const noInternOdds = odds(underemployed) / Math.pow(or, q);
  return prob(internship === 'none' ? noInternOdds : noInternOdds * or);
}

/* P1: chance your first job needs your degree. */
export function degreeJobOdds(model: ModelFile, data: GameData, c: Choices): number {
  if (c.offer === 'accept') {
    return 0;
  }
  const r = modelRates(model, data, c);
  return (1 - r.unemployed) * (1 - withInternship(r.underemployed, c.internship));
}

/* P10: chance of a degree-level job 10 years after graduating. */
export function longRunOdds(p1: number): number {
  return p1 * RESEARCH.stayCollegeLevel + (1 - p1) * RESEARCH.leaveUnderemployment;
}

export interface Option {
  label: string;
  value: string;
}

export interface Decision {
  key: keyof Choices;
  when: string;
  text: string;
  options: Option[];               // empty = dropdown of majors
  affectsScore: boolean;
  fact: (ctx: FactContext) => string;
  explore: { section: string; label: string };   // "See the data" link to an Explore section
}

export interface FactContext {
  choice: string;
  choices: Choices;
  data: GameData;
  deltas: Record<string, number>;  // per option: score (percentage points) with that option minus score before deciding
  rates: { unemployed: number; underemployed: number };
}

const pts = (x: number) => `${x >= 0 ? '+' : ''}${(x ?? 0).toFixed(1)} percentage points`;
const ptsPhrase = (x: number) => x >= 0.05
  ? `raises your chances by ${x.toFixed(1)} percentage points`
  : x <= -0.05 ? `shifts your chances by ${x.toFixed(1)} percentage points` : 'keeps your chances about the same';

export const DECISIONS: Decision[] = [
  {
    key: 'major',
    explore: { section: 'explore-majors', label: 'Underemployment by major' },
    when: 'FRESHMAN FALL',
    text: 'Time to pick a major.',
    options: [],
    affectsScore: true,
    fact: ({ choice, data }) => {
      const m = data.majors[choice];
      return `Here is where ${choice} graduates aged 22 to 27 land: ${m.underemployed}% of those working are underemployed (in jobs that do not require their degree), and ${m.unemployed}% of those looking for work are unemployed. The choices ahead can shift these numbers. Source: our analysis of the Census American Community Survey.`;
    }
  },
  {
    key: 'aiClass',
    explore: { section: 'explore-ai', label: 'Youth unemployment before and after AI' },
    when: 'FRESHMAN SPRING',
    text: 'You need one more elective.',
    options: [
      { label: 'A CHALLENGING MACHINE LEARNING (AI) CLASS', value: 'challenge' },
      { label: 'A CLASS YOU KNOW YOU WILL ACE', value: 'easy' }
    ],
    affectsScore: false,
    fact: ({ choice }) => choice === 'challenge'
      ? 'Job postings that ask for AI skills pay a 56% premium over the same job without them (PwC, 2025 Global AI Jobs Barometer).\nNo study ties a single class to job outcomes. Your chances hold steady.'
      : 'GPA still matters to many employers: 42% screen new graduates by GPA, though that is down from about three-quarters in 2019 (NACE Job Outlook 2026).\nNo study ties a single class to job outcomes. Your chances hold steady.'
  },
  {
    key: 'secondMajor',
    explore: { section: 'explore-calculator', label: 'Try a second major in the odds calculator' },
    when: 'SOPHOMORE YEAR',
    text: 'Add a second major?',
    options: [
      { label: 'NO, ONE MAJOR', value: 'None' },
      { label: 'MATH & STATISTICS', value: 'Mathematics & Statistics' },
      { label: 'COMPUTER SCIENCE', value: 'Computer & Information Sciences' },
      { label: 'BUSINESS', value: 'Business' },
      { label: 'OTHER', value: ANY_SECOND_MAJOR }
    ],
    affectsScore: true,
    fact: ({ choice, deltas }) => choice === 'None'
      ? 'One major is the most common path: about 7 in 8 young graduates in our data have one. Your chances hold steady.'
      : choice === ANY_SECOND_MAJOR
        ? `Averaged across the 12 most common second majors (weighted by how often graduates choose them, excluding your first major), a second major ${ptsPhrase(deltas[choice])} in our model.`
        : `In our model, a second major in this field ${ptsPhrase(deltas[choice])} (chance of a first job that uses your degree).`
  },
  {
    key: 'internship',
    explore: { section: 'explore-majors', label: 'How much an internship lowers underemployment' },
    when: 'SUMMER BEFORE SENIOR YEAR',
    text: 'How do you spend the summer?',
    options: [
      { label: 'PAID INTERNSHIP', value: 'paid' },
      { label: 'UNPAID INTERNSHIP', value: 'unpaid' },
      { label: 'REGULAR SUMMER JOB', value: 'none' }
    ],
    affectsScore: true,
    fact: ({ choice, deltas }) => ({
      paid: `Paid interns averaged 1.01 job offers before graduating and a $68,041 starting salary, compared with 0.74 offers and $55,924 without an internship (NACE 2024). Any internship lowers the odds of underemployment by 49% (Strada & Burning Glass 2024).`,
      unpaid: `Any internship lowers the odds of underemployment by 49% (Strada & Burning Glass 2024). Tip: paid internships tend to bring more job offers before graduation, 1.01 on average vs 0.66 for unpaid (NACE 2024).`,
      none: `Summer jobs build real skills. For jobs that use your degree, internships make a big difference: 41% of interns were underemployed five years out, compared with 54% without one (Strada & Burning Glass 2024).`
    } as Record<string, string>)[choice]
  },
  {
    key: 'aiCert',
    explore: { section: 'explore-ai', label: 'Youth unemployment before and after AI' },
    when: 'SENIOR FALL',
    text: 'Your school offers a free AI certificate course.',
    options: [
      { label: 'TAKE IT', value: 'yes' },
      { label: 'SKIP IT', value: 'no' }
    ],
    affectsScore: false,
    fact: ({ choices, data }) => {
      const share = data.majors[choices.major ?? '']?.ai_exposed_share;
      const mine = share == null ? '' : ` In your major, ${share}% of young graduates work in jobs where AI can speed up at least half the tasks (our analysis of Eloundou et al. 2023).`;
      return `AI is reshaping entry-level work: since generative AI spread, early-career employment in the most AI-exposed jobs fell 13% relative to other jobs (Brynjolfsson, Chandar & Chen 2025), which makes AI skills worth building.${mine}\nCertificates have not been studied for new graduates yet. Your chances hold steady.`;
    }
  },
  {
    key: 'search',
    explore: { section: 'explore-calculator', label: 'Compare states in the odds calculator' },
    when: 'SENIOR FALL',
    text: 'Where do you look for jobs?',
    options: [
      { label: 'ONLY NORTH CAROLINA', value: 'home' },
      { label: 'ANYWHERE IN THE US', value: 'anywhere' }
    ],
    affectsScore: true,
    fact: ({ choice, deltas }) => choice === 'home'
      ? `Staying close to home matters to a lot of people: 84% of graduates say cost of living shapes whether they would move (NACE 2024).`
      : `Averaged over where graduates actually live, a national search ${ptsPhrase(deltas['anywhere'])} compared with staying in North Carolina (our model).`
  },
  {
    key: 'grad',
    explore: { section: 'explore-calculator', label: 'Try a graduate degree in the odds calculator' },
    when: 'SENIOR WINTER',
    text: 'Apply to grad school, or go straight to work?',
    options: [
      { label: 'GRAD SCHOOL', value: 'yes' },
      { label: 'STRAIGHT TO WORK', value: 'no' }
    ],
    affectsScore: true,
    fact: ({ choice, deltas }) => choice === 'yes'
      ? `In our model, a graduate degree ${ptsPhrase(deltas['yes'])} of a job that uses your education. Worth weighing against tuition and time out of work, which this score does not count.`
      : `Going straight to work means earning sooner. For reference, a graduate degree ${ptsPhrase(deltas['yes'])} in our model, with tuition and time out of work to weigh.`
  },
  {
    key: 'offer',
    explore: { section: 'explore-underemployment', label: 'What young US graduates are doing' },
    when: 'SENIOR SPRING',
    text: 'You get an offer for a job that does not require a degree.',
    options: [
      { label: 'ACCEPT IT', value: 'accept' },
      { label: 'KEEP SEARCHING', value: 'keep' }
    ],
    affectsScore: true,
    fact: ({ choice, rates }) => choice === 'accept'
      ? 'A paycheck and experience count. Worth knowing: first jobs tend to set the track, and 73% of graduates who start in a job that does not require a degree are still in one 10 years later (Strada & Burning Glass 2024). Keeping an eye out for degree-level roles helps you switch tracks.'
      : `Graduates who start in a job that uses their degree are 3.5 times less likely to be underemployed 10 years later (Strada & Burning Glass 2024). Searching longer carries its own risk: ${(rates.unemployed * 100).toFixed(1)}% of graduates on your path are unemployed at 24 (our model).`
  }
];

/* Score change (percentage points) for each option of a decision, vs. the score before deciding. */
export function optionDeltas(model: ModelFile, data: GameData, c: Choices, d: Decision): Record<string, number> {
  if (!d.affectsScore || d.key === 'major' || d.key === 'offer') {
    return {};
  }
  const before = { ...c, [d.key]: undefined };
  const base = degreeJobOdds(model, data, before);
  return Object.fromEntries(d.options.map(o =>
    [o.value, (degreeJobOdds(model, data, { ...before, [d.key]: o.value }) - base) * 100]));
}
