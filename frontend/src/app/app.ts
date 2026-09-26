import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';

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

  setView(view: 'game' | 'explore'): void {
    this.currentView = view;

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