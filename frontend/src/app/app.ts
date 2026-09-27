import { CommonModule } from '@angular/common';
import { Component, computed, signal } from '@angular/core';

import { encode, FairnessRow, ModelFile, predict } from './model';

type ProfileKey =
  | 'major' | 'second_major' | 'sex' | 'race'
  | 'born_us' | 'state' | 'moved_states' | 'grad_degree';
type Profile = Record<ProfileKey, string>;

interface Odds {
  unemployed: number;
  neet: number;
  underemployed: number;
}

interface Choice {
  label: string;
  jobDelta: number;
  wellbeingDelta: number;
  consequence: string;
}

interface Scenario {
  month: string;
  countdown: string;
  text: string;
  choices: Choice[];
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  currentView: 'game' | 'explore' = 'game';

  currentScenario = 0;

  jobScore = 0;
  wellbeing = 70;

  answers: Record<number, number> = {};

  scenarios: Scenario[] = [
    {
      month: 'AUGUST',
      countdown: '9 MONTHS UNTIL GRADUATION',
      text: 'Senior year begins. When do you start thinking about finding a job?',
      choices: [
        {
          label: 'START NOW',
          jobDelta: 2,
          wellbeingDelta: -3,
          consequence: 'You begin your job search early.'
        },
        {
          label: 'WAIT',
          jobDelta: 0,
          wellbeingDelta: 2,
          consequence: 'You decide there is still plenty of time.'
        }
      ]
    },

    {
      month: 'SEPTEMBER',
      countdown: '8 MONTHS UNTIL GRADUATION',
      text: 'Your school is holding a career fair.',
      choices: [
        {
          label: 'ATTEND',
          jobDelta: 3,
          wellbeingDelta: -2,
          consequence: 'You meet employers and learn about new opportunities.'
        },
        {
          label: 'SKIP',
          jobDelta: 0,
          wellbeingDelta: 1,
          consequence: 'You skip the fair and continue with your normal schedule.'
        }
      ]
    },

    {
      month: 'OCTOBER',
      countdown: '7 MONTHS UNTIL GRADUATION',
      text: 'Job applications are starting to open.',
      choices: [
        {
          label: 'START APPLYING',
          jobDelta: 3,
          wellbeingDelta: -4,
          consequence: 'You submit your first applications.'
        },
        {
          label: 'WAIT UNTIL LATER',
          jobDelta: -1,
          wellbeingDelta: 2,
          consequence: 'You decide to wait before applying.'
        }
      ]
    },

    {
      month: 'NOVEMBER',
      countdown: '6 MONTHS UNTIL GRADUATION',
      text: 'School and the job search are becoming overwhelming.',
      choices: [
        {
          label: 'PUSH THROUGH',
          jobDelta: 2,
          wellbeingDelta: -12,
          consequence: 'You keep applying, but your stress increases.'
        },
        {
          label: 'SLOW DOWN',
          jobDelta: -1,
          wellbeingDelta: 8,
          consequence: 'You give yourself more time to recover.'
        },
        {
          label: 'ASK FOR SUPPORT',
          jobDelta: 1,
          wellbeingDelta: 10,
          consequence: 'You reach out for support while continuing your search.'
        }
      ]
    },

    {
      month: 'DECEMBER',
      countdown: '5 MONTHS UNTIL GRADUATION',
      text: 'You still do not have a job offer.',
      choices: [
        {
          label: 'KEEP APPLYING',
          jobDelta: 3,
          wellbeingDelta: -5,
          consequence: 'You continue applying despite the uncertainty.'
        },
        {
          label: 'TAKE A BREAK',
          jobDelta: -1,
          wellbeingDelta: 7,
          consequence: 'You step away from the job search for a while.'
        }
      ]
    },

    {
      month: 'JANUARY',
      countdown: '4 MONTHS UNTIL GRADUATION',
      text: 'A new recruiting cycle begins.',
      choices: [
        {
          label: 'EXPAND YOUR SEARCH',
          jobDelta: 3,
          wellbeingDelta: -3,
          consequence: 'You begin considering a wider range of opportunities.'
        },
        {
          label: 'KEEP YOUR SEARCH NARROW',
          jobDelta: 0,
          wellbeingDelta: 1,
          consequence: 'You continue focusing on the jobs you originally wanted.'
        }
      ]
    },

    {
      month: 'FEBRUARY',
      countdown: '3 MONTHS UNTIL GRADUATION',
      text: 'How do you want to find new opportunities?',
      choices: [
        {
          label: 'NETWORK',
          jobDelta: 2,
          wellbeingDelta: -2,
          consequence: 'You begin building connections with people who may know about opportunities.'
        },
        {
          label: 'APPLY ONLINE',
          jobDelta: 1,
          wellbeingDelta: 0,
          consequence: 'You focus on finding opportunities online.'
        },
        {
          label: 'DO BOTH',
          jobDelta: 3,
          wellbeingDelta: -5,
          consequence: 'You use multiple strategies at the same time.'
        }
      ]
    },

    {
      month: 'MARCH',
      countdown: '2 MONTHS UNTIL GRADUATION',
      text: 'Graduation is getting closer.',
      choices: [
        {
          label: 'APPLY BROADLY',
          jobDelta: 3,
          wellbeingDelta: -4,
          consequence: 'You increase the number of opportunities available to you.'
        },
        {
          label: 'ONLY APPLY TO IDEAL JOBS',
          jobDelta: 0,
          wellbeingDelta: 1,
          consequence: 'You keep your search focused on the jobs you want most.'
        }
      ]
    },

    {
      month: 'APRIL',
      countdown: '1 MONTH UNTIL GRADUATION',
      text: 'You receive a job offer, but it is not exactly what you hoped for.',
      choices: [
        {
          label: 'ACCEPT',
          jobDelta: 5,
          wellbeingDelta: 3,
          consequence: 'You secure a job before graduation.'
        },
        {
          label: 'KEEP SEARCHING',
          jobDelta: 0,
          wellbeingDelta: -4,
          consequence: 'You turn down the offer and continue searching.'
        }
      ]
    }
  ];

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

  setView(view: 'game' | 'explore'): void {
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

  selectChoice(scenarioIndex: number, choiceIndex: number): void {
    const scenario = this.scenarios[scenarioIndex];

    const previousChoiceIndex = this.answers[scenarioIndex];

    if (previousChoiceIndex !== undefined) {
      const previousChoice = scenario.choices[previousChoiceIndex];

      this.jobScore -= previousChoice.jobDelta;
      this.wellbeing -= previousChoice.wellbeingDelta;
    }

    const choice = scenario.choices[choiceIndex];

    this.answers[scenarioIndex] = choiceIndex;

    this.jobScore += choice.jobDelta;
    this.wellbeing += choice.wellbeingDelta;

    this.wellbeing = Math.max(
      0,
      Math.min(100, this.wellbeing)
    );
  }

  selectedChoice(scenarioIndex: number): Choice | null {
    const choiceIndex = this.answers[scenarioIndex];

    if (choiceIndex === undefined) {
      return null;
    }

    return this.scenarios[scenarioIndex].choices[choiceIndex];
  }

  onStoryScroll(event: Event): void {
    const container = event.target as HTMLElement;

    const scenes = Array.from(
      container.querySelectorAll<HTMLElement>('.question-scene')
    );

    if (scenes.length === 0) {
      return;
    }

    const containerTop =
      container.getBoundingClientRect().top;

    let closestIndex = 0;
    let closestDistance = Infinity;

    scenes.forEach((scene, index) => {
      const distance = Math.abs(
        scene.getBoundingClientRect().top -
        containerTop
      );

      if (distance < closestDistance) {
        closestDistance = distance;
        closestIndex = index;
      }
    });

    this.currentScenario = closestIndex;
  }
}