import { CommonModule } from '@angular/common';
import { afterNextRender, Component, computed, signal } from '@angular/core';

import {
  Choices, Decision, DECISIONS, degreeJobOdds, GameData,
  longRunOdds, modelRates, optionDeltas, RESEARCH, SOURCES
} from './game';
import { encode, FairnessRow, ModelFile, predict } from './model';

type ProfileKey =
  | 'major' | 'second_major' | 'sex' | 'race'
  | 'born_us' | 'state' | 'moved_states' | 'grad_degree';
type Profile = Record<ProfileKey, string>;

type View = 'game' | 'explore' | 'resources';

interface Odds {
  unemployed: number;
  neet: number;
  underemployed: number;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  currentView: View = 'game';

  /* ---------- Game: every decision maps to data (see game.ts) ---------- */

  readonly decisions = DECISIONS;
  readonly research = RESEARCH;
  readonly sources = SOURCES;

  gameData = signal<GameData | null>(null);
  choices = signal<Choices>({});

  constructor() {
    afterNextRender(() => {
      this.loadModel();
      this.loadGameData();
    });
  }

  ready = computed(() => !!this.model() && !!this.gameData());

  majors = computed(() => Object.keys(this.gameData()?.majors ?? {}).sort());

  answeredCount = computed(() => {
    const c = this.choices();
    const first = this.decisions.findIndex(d => c[d.key] === undefined);
    return first < 0 ? this.decisions.length : first;
  });

  /* Only answered decisions plus the next one exist, so you can't skip ahead. */
  visibleDecisions = computed(() =>
    this.ready() ? this.decisions.slice(0, Math.min(this.answeredCount() + 1, this.decisions.length)) : []);

  gameDone = computed(() => this.answeredCount() === this.decisions.length);

  score = computed(() => {
    const model = this.model();
    const data = this.gameData();
    const c = this.choices();
    return model && data && c.major ? degreeJobOdds(model, data, c) * 100 : null;
  });

  longRun = computed(() => {
    const s = this.score();
    return s === null ? null : longRunOdds(s / 100) * 100;
  });

  /* Fact shown after each answered decision. */
  facts = computed<Record<string, string>>(() => {
    const model = this.model();
    const data = this.gameData();
    const c = this.choices();

    if (!model || !data) {
      return {};
    }

    const out: Record<string, string> = {};
    for (const d of this.decisions) {
      const choice = c[d.key];
      if (choice === undefined) {
        continue;
      }
      out[d.key] = d.fact({
        choice,
        choices: c,
        data,
        deltas: optionDeltas(model, data, c, d),
        rates: modelRates(model, data, c)
      });
    }
    return out;
  });

  loadGameData(): void {
    if (this.gameData()) {
      return;
    }

    fetch('game_data.json')
      .then(response => response.json())
      .then((data: GameData) => this.gameData.set(data))
      .catch(error => console.error('Could not load game_data.json', error));
  }

  /* A second major can never repeat the first major. */
  optionsFor(d: Decision) {
    const major = this.choices().major;
    return d.key === 'secondMajor' ? d.options.filter(o => o.value !== major) : d.options;
  }

  /* Answers are final: once a decision is answered it cannot be changed (Play again resets). */
  choose(d: Decision, value: string): void {
    if (this.choices()[d.key] !== undefined) {
      return;
    }
    this.choices.update(c => {
      const next = { ...c, [d.key]: value };
      if (d.key === 'major' && next.secondMajor === value) {
        next.secondMajor = 'None';
      }
      return next;
    });
  }

  /* "See the data" link after a decision: fade into Explore, then glide to the matching section. */
  goToExplore(sectionId: string): void {
    this.setView('explore');
    setTimeout(() =>
      document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 350);
  }

  /* "Look at the data behind this" on the graduation screen: open Explore at the top. */
  exploreFromGraduation(): void {
    this.setView('explore');
  }

  /* ---------- Resources page (opened from the graduation screen) ---------- */

  readonly resourceGroups: { title: string; links: { name: string; url: string; note?: string }[] }[] = [
    {
      title: 'UNC-CH',
      links: [
        { name: 'UNC Heels Engage Network', url: 'https://careers.unc.edu/resources/heels-engage-network/' },
        { name: 'UNC Career Center', url: 'https://careers.unc.edu/resources/heels-engage-network/' },
        { name: 'Career Coaching', url: 'https://careers.unc.edu/students/schedule-an-appointment/' },
        { name: 'UNC University Library workshops and events', url: 'https://calendar.lib.unc.edu/calendar/' },
        { name: 'UNC Career Hub', url: 'https://careerhub.unc.edu/career-resources/find-a-career-office/' },
        { name: 'LinkedIn Learning through UNC-CH', url: 'https://careerhub.unc.edu/career-resources/find-a-career-office/' }
      ]
    },
    {
      title: 'LOCAL / NC',
      links: [
        { name: 'NCWorks', url: 'https://www.ncworks.gov/vosnet/default.aspx', note: 'Help registering with and using NCWorks Online' },
        { name: 'NCWorks NextGen Program', url: 'https://nccareers.org/ncworks-nextgen-program' },
        { name: 'NCCareers', url: 'https://nccareers.org/' }
      ]
    }
  ];

  restartGame(): void {
    this.choices.set({});
    document.querySelector('.story')?.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /* ---------- Explore: odds calculator (model runs in the browser) ---------- */

  readonly outcomes: (keyof Odds)[] = ['unemployed', 'neet', 'underemployed'];

  readonly profileFields: { key: ProfileKey; label: string }[] = [
    { key: 'major', label: 'MAJOR' },
    { key: 'second_major', label: 'SECOND MAJOR' },
    { key: 'sex', label: 'GENDER' },
    { key: 'race', label: 'RACE / ETHNICITY' },
    { key: 'born_us', label: 'BORN IN THE US?' },
    { key: 'state', label: 'STATE YOU LIVE IN' },
    { key: 'moved_states', label: 'OUTSIDE HOME STATE?' },
    { key: 'grad_degree', label: 'GRADUATE DEGREE?' }
  ];

  model = signal<ModelFile | null>(null);
  modelFailed = signal(false);

  profile = signal<Profile>({
    major: 'Business',
    second_major: 'None',
    sex: 'Female',
    race: 'White',
    born_us: 'Yes',
    state: 'North Carolina',
    moved_states: 'No',
    grad_degree: 'No'
  });

  compareState = signal('California');

  myOdds = computed(() => this.oddsFor(this.profile()));

  bornElsewhereOdds = computed(() => {
    const born = this.profile().born_us === 'Yes' ? 'No' : 'Yes';
    return this.oddsFor({ ...this.profile(), born_us: born, moved_states: 'No' });
  });

  otherStateOdds = computed(() => this.oddsFor(this.moveTo(this.compareState())));

  fairnessRows = computed(() => {
    const data = this.model();

    if (!data) {
      return [];
    }

    const names: Record<string, string> = { Yes: 'Born in the US', No: 'Born abroad' };
    return data.outcomes['unemployed'].fairness.map((row, i) => ({
      label: row.attribute === 'born_us' ? names[row.group] : row.group,
      cells: this.outcomes.map(o => data.outcomes[o].fairness[i])
    }));
  });

  /* The two groups where predicted and actual rates differ most. */
  largestGaps = computed(() => {
    const data = this.model();

    if (!data) {
      return [];
    }

    return this.outcomes
      .flatMap(o => data.outcomes[o].fairness.map(row => ({ outcome: o, row })))
      .sort((x, y) => this.gap(y.row) - this.gap(x.row))
      .slice(0, 2);
  });

  gap(row: FairnessRow): number {
    return Math.abs(row.predicted - row.actual);
  }

  loadModel(): void {
    if (this.model()) {
      return;
    }

    this.modelFailed.set(false);

    fetch('model.json')
      .then(response => response.json())
      .then((data: ModelFile) => this.model.set(data))
      .catch(error => {
        console.error('Could not load model.json', error);
        this.modelFailed.set(true);
      });
  }

  /* Dropdown options, with "None" first for the second major. */
  options(data: ModelFile, key: ProfileKey): string[] {
    const list = data.categories[key];
    return list.includes('None') ? ['None', ...list.filter(o => o !== 'None')] : list;
  }

  setProfile(key: ProfileKey, value: string): void {
    this.profile.update(profile => ({ ...profile, [key]: value }));
  }

  moveTo(state: string): Profile {
    const profile = this.profile();
    return {
      ...profile,
      state,
      moved_states: profile.born_us === 'Yes' ? 'Yes' : 'No'
    };
  }

  oddsFor(profile: Profile): Odds | null {
    const data = this.model();

    if (!data) {
      return null;
    }

    const row = encode(data, { ...profile, year: '2023', age: 24 });
    const percent = (o: keyof Odds) =>
      Math.round(predict(data.outcomes[o], row) * 1000) / 10;

    return {
      unemployed: percent('unemployed'),
      neet: percent('neet'),
      underemployed: percent('underemployed')
    };
  }

  setView(view: View): void {
    this.currentView = view;

    if (view === 'explore') {
      this.loadModel();
    }

    setTimeout(() => {
      const scrollContainer = document.querySelector(
        view === 'game' ? '.story' : '.explore-page'
      ) as HTMLElement | null;

      scrollContainer?.scrollTo({
        top: 0,
        behavior: 'instant' as ScrollBehavior
      });
    });
  }
}