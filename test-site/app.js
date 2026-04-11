(() => {
  const ACCOUNTS_KEY = "accounts_v1";
  const PROFILES_KEY = "profiles_v1";
  const POSTS_KEY = "posts_v1";
  const AUTH_USER_KEY = "auth_user";
  const POST_MAX_LEN = 140;
  const FAVORITE_QUOTE_MAX_LEN = 500;
  const TIMEZONE_OPTIONS = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "America/Honolulu",
    "America/Toronto",
    "America/Vancouver",
    "America/Mexico_City",
    "America/Sao_Paulo",
    "America/Buenos_Aires",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Moscow",
    "Africa/Johannesburg",
    "Africa/Cairo",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Bangkok",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Australia/Sydney",
    "Pacific/Auckland",
  ];
  const TIMEZONE_SET = new Set(TIMEZONE_OPTIONS);
  const ABOUT_ME_MAX_LEN = 1000;
  const DISPLAY_NAME_MAX_LEN = 32;
  const USA_COUNTRY = "United States of America";
  const COUNTRY_OPTIONS = [
    USA_COUNTRY,
    "Afghanistan",
    "Albania",
    "Algeria",
    "Andorra",
    "Angola",
    "Argentina",
    "Armenia",
    "Australia",
    "Austria",
    "Azerbaijan",
    "Bahrain",
    "Bangladesh",
    "Belarus",
    "Belgium",
    "Belize",
    "Bolivia",
    "Bosnia and Herzegovina",
    "Botswana",
    "Brazil",
    "Bulgaria",
    "Cambodia",
    "Cameroon",
    "Canada",
    "Chile",
    "China",
    "Colombia",
    "Costa Rica",
    "Croatia",
    "Cuba",
    "Cyprus",
    "Czech Republic",
    "Denmark",
    "Dominican Republic",
    "Ecuador",
    "Egypt",
    "El Salvador",
    "Estonia",
    "Ethiopia",
    "Finland",
    "France",
    "Georgia",
    "Germany",
    "Ghana",
    "Greece",
    "Guatemala",
    "Honduras",
    "Hungary",
    "Iceland",
    "India",
    "Indonesia",
    "Iran",
    "Iraq",
    "Ireland",
    "Israel",
    "Italy",
    "Jamaica",
    "Japan",
    "Jordan",
    "Kazakhstan",
    "Kenya",
    "Kuwait",
    "Latvia",
    "Lebanon",
    "Lithuania",
    "Luxembourg",
    "Malaysia",
    "Mexico",
    "Morocco",
    "Nepal",
    "Netherlands",
    "New Zealand",
    "Nigeria",
    "Norway",
    "Pakistan",
    "Panama",
    "Peru",
    "Philippines",
    "Poland",
    "Portugal",
    "Qatar",
    "Romania",
    "Saudi Arabia",
    "Serbia",
    "Singapore",
    "Slovakia",
    "Slovenia",
    "South Africa",
    "South Korea",
    "Spain",
    "Sri Lanka",
    "Sweden",
    "Switzerland",
    "Taiwan",
    "Thailand",
    "Tunisia",
    "Turkey",
    "Ukraine",
    "United Arab Emirates",
    "United Kingdom",
    "Uruguay",
    "Venezuela",
    "Vietnam",
    "Zimbabwe",
  ];
  const US_STATE_OPTIONS = [
    "Alabama",
    "Alaska",
    "Arizona",
    "Arkansas",
    "California",
    "Colorado",
    "Connecticut",
    "Delaware",
    "Florida",
    "Georgia",
    "Hawaii",
    "Idaho",
    "Illinois",
    "Indiana",
    "Iowa",
    "Kansas",
    "Kentucky",
    "Louisiana",
    "Maine",
    "Maryland",
    "Massachusetts",
    "Michigan",
    "Minnesota",
    "Mississippi",
    "Missouri",
    "Montana",
    "Nebraska",
    "Nevada",
    "New Hampshire",
    "New Jersey",
    "New Mexico",
    "New York",
    "North Carolina",
    "North Dakota",
    "Ohio",
    "Oklahoma",
    "Oregon",
    "Pennsylvania",
    "Rhode Island",
    "South Carolina",
    "South Dakota",
    "Tennessee",
    "Texas",
    "Utah",
    "Vermont",
    "Virginia",
    "Washington",
    "West Virginia",
    "Wisconsin",
    "Wyoming",
  ];
  const COUNTRY_SET = new Set(COUNTRY_OPTIONS);
  const STATE_SET = new Set(US_STATE_OPTIONS);
  const SEEDED_ACCOUNTS = [{ username: "demo", password: "demo123" }];
  const QUIZ_BANK_SIZE = 20;
  const QUIZ_QUESTION_COUNT = 4;
  const QUIZ_OPTIONS_COUNT = 4;
  const QUIZ_TRANSITION_MS = 320;

  function buildAnswerSet(correctValue, seed) {
    const wrongAnswers = [];
    let delta = 1;
    while (wrongAnswers.length < QUIZ_OPTIONS_COUNT - 1) {
      const sign = delta % 2 === 0 ? -1 : 1;
      const candidate = correctValue + sign * (seed + delta);
      if (
        candidate > 0 &&
        candidate !== correctValue &&
        !wrongAnswers.includes(candidate)
      ) {
        wrongAnswers.push(candidate);
      }
      delta += 1;
    }

    const correctIndex = seed % QUIZ_OPTIONS_COUNT;
    const answers = [];
    let wrongIdx = 0;
    for (let i = 0; i < QUIZ_OPTIONS_COUNT; i += 1) {
      if (i === correctIndex) {
        answers.push(String(correctValue));
      } else {
        answers.push(String(wrongAnswers[wrongIdx]));
        wrongIdx += 1;
      }
    }
    return { answers, correctIndex };
  }

  function buildGeneratedQuiz(quizNumber) {
    const id = `quiz-${String(quizNumber).padStart(2, "0")}`;
    const title = `Quick Quiz ${quizNumber}`;
    const questionSpecs = [
      {
        prompt: `What is ${quizNumber + 3} + ${quizNumber + 5}?`,
        correctValue: quizNumber + 3 + (quizNumber + 5),
      },
      {
        prompt: `What is ${quizNumber + 12} - ${quizNumber + 4}?`,
        correctValue: quizNumber + 12 - (quizNumber + 4),
      },
      {
        prompt: `What is ${quizNumber + 1} x 3?`,
        correctValue: (quizNumber + 1) * 3,
      },
      {
        prompt: `What is ${(quizNumber + 2) * 4} / 4?`,
        correctValue: quizNumber + 2,
      },
    ];

    return {
      id,
      title,
      questions: questionSpecs.map((spec, idx) => {
        const { answers, correctIndex } = buildAnswerSet(
          spec.correctValue,
          quizNumber + idx + 3
        );
        return {
          prompt: spec.prompt,
          answers,
          correctIndex,
        };
      }),
    };
  }

  const QUIZ_BANK = Array.from({ length: QUIZ_BANK_SIZE }, (_, idx) =>
    buildGeneratedQuiz(idx + 1)
  );

  function validateQuizBank(quizBank) {
    if (!Array.isArray(quizBank) || quizBank.length !== QUIZ_BANK_SIZE) {
      throw new Error(`Quiz bank must contain exactly ${QUIZ_BANK_SIZE} quizzes.`);
    }
    const quizIds = new Set();
    for (const quiz of quizBank) {
      if (typeof quiz?.id !== "string" || !quiz.id) {
        throw new Error("Each quiz must include a non-empty id.");
      }
      if (quizIds.has(quiz.id)) {
        throw new Error(`Duplicate quiz id: ${quiz.id}`);
      }
      quizIds.add(quiz.id);
      if (
        !Array.isArray(quiz.questions) ||
        quiz.questions.length !== QUIZ_QUESTION_COUNT
      ) {
        throw new Error(
          `Quiz ${quiz.id} must include ${QUIZ_QUESTION_COUNT} questions.`
        );
      }
      for (const question of quiz.questions) {
        if (typeof question?.prompt !== "string" || !question.prompt.trim()) {
          throw new Error(`Quiz ${quiz.id} has a question with missing prompt.`);
        }
        if (
          !Array.isArray(question.answers) ||
          question.answers.length !== QUIZ_OPTIONS_COUNT
        ) {
          throw new Error(
            `Quiz ${quiz.id} question must include ${QUIZ_OPTIONS_COUNT} answers.`
          );
        }
        if (
          !Number.isInteger(question.correctIndex) ||
          question.correctIndex < 0 ||
          question.correctIndex >= QUIZ_OPTIONS_COUNT
        ) {
          throw new Error(`Quiz ${quiz.id} question has invalid correctIndex.`);
        }
      }
    }
  }

  validateQuizBank(QUIZ_BANK);

  function normalizeUsername(raw) {
    return (raw || "").trim();
  }

  function canonicalUsername(raw) {
    return normalizeUsername(raw).toLowerCase();
  }

  function loadAccounts() {
    try {
      const raw = localStorage.getItem(ACCOUNTS_KEY);
      if (!raw) {
        return [...SEEDED_ACCOUNTS];
      }
      const parsed = JSON.parse(raw);
      const accounts = Array.isArray(parsed?.accounts) ? parsed.accounts : null;
      if (!accounts) {
        return [...SEEDED_ACCOUNTS];
      }
      const normalized = [];
      for (const acct of accounts) {
        const username = normalizeUsername(acct?.username || "");
        const password = String(acct?.password || "");
        if (!username || !password) {
          continue;
        }
        normalized.push({ username, password });
      }
      if (normalized.length <= 0) {
        return [...SEEDED_ACCOUNTS];
      }
      return normalized;
    } catch {
      return [...SEEDED_ACCOUNTS];
    }
  }

  function saveAccounts(accounts) {
    localStorage.setItem(ACCOUNTS_KEY, JSON.stringify({ accounts }));
  }

  function truncateAboutMe(value) {
    return String(value || "").slice(0, ABOUT_ME_MAX_LEN);
  }

  function normalizeDisplayName(value) {
    return String(value || "").trim().slice(0, DISPLAY_NAME_MAX_LEN);
  }

  function normalizeCountry(value) {
    const candidate = String(value || "").trim();
    return COUNTRY_SET.has(candidate) ? candidate : "";
  }

  function normalizeState(value) {
    const candidate = String(value || "").trim();
    return STATE_SET.has(candidate) ? candidate : "";
  }

  function normalizeTimezone(value) {
    const candidate = String(value || "").trim();
    return TIMEZONE_SET.has(candidate) ? candidate : "";
  }

  function truncateFavoriteQuote(value) {
    return String(value || "").slice(0, FAVORITE_QUOTE_MAX_LEN);
  }

  function normalizeSocialLinks(links) {
    const src =
      links && typeof links === "object" && !Array.isArray(links) ? links : {};
    return {
      linkedin: String(src.linkedin || "").trim(),
      xTwitter: String(src.xTwitter || "").trim(),
      instagram: String(src.instagram || "").trim(),
      facebook: String(src.facebook || "").trim(),
      github: String(src.github || "").trim(),
    };
  }

  function normalizeSavedProfile(entry) {
    const aboutMe = truncateAboutMe(entry?.aboutMe || "");
    const country = normalizeCountry(entry?.country || "");
    const state = country === USA_COUNTRY ? normalizeState(entry?.state || "") : "";
    const displayName = normalizeDisplayName(entry?.displayName || "");
    const birthday = String(entry?.birthday || "").trim();
    const hometown = String(entry?.hometown || "").trim();
    const address = String(entry?.address || "").trim();
    const timezone = normalizeTimezone(entry?.timezone || "");
    const favoriteColor = String(entry?.favoriteColor || "").trim();
    const occupation = String(entry?.occupation || "").trim();
    const pronouns = String(entry?.pronouns || "").trim();
    const favoriteQuote = truncateFavoriteQuote(entry?.favoriteQuote || "");
    const socialLinks = normalizeSocialLinks(entry?.socialLinks);
    return {
      aboutMe,
      country,
      state,
      displayName,
      birthday,
      hometown,
      address,
      timezone,
      favoriteColor,
      occupation,
      pronouns,
      favoriteQuote,
      socialLinks,
    };
  }

  function loadProfiles() {
    try {
      const raw = localStorage.getItem(PROFILES_KEY);
      if (!raw) {
        return { profiles: {} };
      }
      const parsed = JSON.parse(raw);
      const profiles = parsed?.profiles;
      if (!profiles || typeof profiles !== "object" || Array.isArray(profiles)) {
        return { profiles: {} };
      }

      const normalizedProfiles = {};
      for (const [rawKey, entry] of Object.entries(profiles)) {
        const key = canonicalUsername(rawKey);
        if (!key) {
          continue;
        }
        normalizedProfiles[key] = normalizeSavedProfile(entry);
      }
      return { profiles: normalizedProfiles };
    } catch {
      return { profiles: {} };
    }
  }

  function saveProfiles(store) {
    localStorage.setItem(PROFILES_KEY, JSON.stringify(store));
  }

  function getSavedProfile(username) {
    const key = canonicalUsername(username);
    if (!key) {
      return normalizeSavedProfile({});
    }
    const store = loadProfiles();
    return normalizeSavedProfile(store.profiles?.[key] || {});
  }

  function getSavedAboutMe(username) {
    return getSavedProfile(username).aboutMe;
  }

  function setSavedProfile(username, entry) {
    const key = canonicalUsername(username);
    if (!key) {
      return;
    }
    const store = loadProfiles();
    if (!store.profiles || typeof store.profiles !== "object") {
      store.profiles = {};
    }
    store.profiles[key] = normalizeSavedProfile(entry);
    saveProfiles(store);
  }

  function setSavedAboutMe(username, aboutMe) {
    const saved = getSavedProfile(username);
    setSavedProfile(username, {
      aboutMe,
      country: saved.country,
      state: saved.state,
    });
  }

  function setSelectOptions(selectEl, options) {
    if (!(selectEl instanceof HTMLSelectElement)) {
      return;
    }
    for (const option of options) {
      const opt = document.createElement("option");
      opt.value = option;
      opt.textContent = option;
      selectEl.appendChild(opt);
    }
  }

  function applyStateVisibility(countrySelect, stateContainer, stateSelect) {
    if (!(countrySelect instanceof HTMLSelectElement)) {
      return;
    }
    const showState = countrySelect.value === USA_COUNTRY;
    if (stateContainer) {
      stateContainer.hidden = !showState;
    }
    if (stateSelect instanceof HTMLSelectElement) {
      stateSelect.disabled = !showState;
      if (!showState) {
        stateSelect.value = "";
      }
    }
  }

  function loadPosts() {
    try {
      const raw = localStorage.getItem(POSTS_KEY);
      if (!raw) {
        return [];
      }
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function savePosts(posts) {
    localStorage.setItem(POSTS_KEY, JSON.stringify(posts));
  }

  function renderFeed(feedContainer, currentUser) {
    const posts = loadPosts();
    posts.sort((a, b) => (a.timestamp > b.timestamp ? -1 : 1));
    feedContainer.innerHTML = "";
    if (posts.length === 0) {
      const empty = document.createElement("p");
      empty.setAttribute("data-testid", "feed-empty");
      empty.textContent = "No posts yet.";
      feedContainer.appendChild(empty);
      return;
    }
    for (const post of posts) {
      const article = document.createElement("article");
      article.setAttribute("data-testid", "feed-post");
      article.dataset.postId = post.id;

      const textEl = document.createElement("p");
      textEl.setAttribute("data-testid", "feed-post-text");
      textEl.textContent = post.text;

      const authorEl = document.createElement("span");
      authorEl.setAttribute("data-testid", "feed-post-author");
      authorEl.textContent = post.author;

      const tsEl = document.createElement("span");
      tsEl.setAttribute("data-testid", "feed-post-timestamp");
      tsEl.textContent = post.timestamp;

      article.appendChild(textEl);
      article.appendChild(authorEl);
      article.appendChild(tsEl);

      if (post.author === currentUser) {
        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.setAttribute("data-testid", "feed-post-delete");
        delBtn.textContent = "Delete";
        delBtn.addEventListener("click", () => {
          const stored = loadPosts();
          savePosts(stored.filter((p) => p.id !== post.id));
          renderFeed(feedContainer, currentUser);
        });
        article.appendChild(delBtn);
      }

      feedContainer.appendChild(article);
    }
  }

  function initializeFeed(currentUser) {
    const feedContainer = document.getElementById("feed-container");
    const postInput = document.getElementById("feed-post-input");
    const postButton = document.getElementById("feed-post-button");

    if (!feedContainer || !postInput || !postButton) {
      return;
    }

    renderFeed(feedContainer, currentUser);

    postButton.addEventListener("click", () => {
      const text = postInput.value.trim();
      if (!text || text.length > POST_MAX_LEN) {
        return;
      }
      const post = {
        id: Date.now().toString(),
        author: currentUser,
        text,
        timestamp: new Date().toISOString(),
      };
      const posts = loadPosts();
      posts.unshift(post);
      savePosts(posts);
      renderFeed(feedContainer, currentUser);
      postInput.value = "";
    });
  }

  function ensureAccountsStore() {
    const accounts = loadAccounts();
    saveAccounts(accounts);
    return accounts;
  }

  function findAccountByUsername(accounts, username) {
    const needle = canonicalUsername(username);
    return accounts.find((acct) => canonicalUsername(acct.username) === needle) || null;
  }

  function validateRegistration(username, password) {
    const cleanName = normalizeUsername(username);
    if (!cleanName) {
      return "Username is required.";
    }
    if (cleanName.length < 3 || cleanName.length > 24) {
      return "Username must be 3-24 characters and contain only letters, numbers, _ or -.";
    }
    if (!/^[A-Za-z0-9_-]+$/.test(cleanName)) {
      return "Username must be 3-24 characters and contain only letters, numbers, _ or -.";
    }
    if (!password) {
      return "Password is required.";
    }
    if (password.length < 8 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      return "Password must be at least 8 characters and include a letter and a number.";
    }
    return null;
  }

  function setError(errorEl, message) {
    if (!errorEl) {
      return;
    }
    if (message) {
      errorEl.textContent = message;
      errorEl.hidden = false;
    } else {
      errorEl.textContent = "";
      errorEl.hidden = true;
    }
  }

  function requireAuthenticatedUser(redirectTarget) {
    const username = localStorage.getItem(AUTH_USER_KEY);
    if (!username) {
      window.location.replace(`index.html?redirect=${redirectTarget}`);
      return null;
    }
    return username;
  }

  function pickRandomQuiz(previousQuizId) {
    if (QUIZ_BANK.length <= 1) {
      return QUIZ_BANK[0];
    }

    let selected = QUIZ_BANK[Math.floor(Math.random() * QUIZ_BANK.length)];
    if (previousQuizId) {
      let guard = 0;
      while (selected.id === previousQuizId && guard < 12) {
        selected = QUIZ_BANK[Math.floor(Math.random() * QUIZ_BANK.length)];
        guard += 1;
      }
    }
    return selected;
  }

  function initializeHomeQuiz() {
    const quizCard = document.getElementById("quiz-card");
    const quizTitle = document.getElementById("quiz-title");
    const quizProgress = document.getElementById("quiz-progress");
    const quizQuestions = document.getElementById("quiz-questions");
    const quizSummary = document.getElementById("quiz-summary");
    const quizPercent = document.getElementById("quiz-percent");
    const quizOverallStatus = document.getElementById("quiz-overall-status");
    const nextQuizButton = document.getElementById("quiz-next-button");

    if (
      !quizCard ||
      !quizTitle ||
      !quizProgress ||
      !quizQuestions ||
      !quizSummary ||
      !quizPercent ||
      !quizOverallStatus ||
      !nextQuizButton
    ) {
      return;
    }

    let activeQuiz = pickRandomQuiz("");
    let selectedAnswers = new Map();
    let inTransition = false;
    let transitionHandle = null;
    const stateClasses = [
      "quiz-state-all-correct",
      "quiz-state-some-correct",
      "quiz-state-none-correct",
    ];

    function clearAggregateState() {
      for (const className of stateClasses) {
        quizCard.classList.remove(className);
      }
    }

    function countCorrectAnswers() {
      let correct = 0;
      for (let idx = 0; idx < activeQuiz.questions.length; idx += 1) {
        const selectedAnswer = selectedAnswers.get(idx);
        if (selectedAnswer === activeQuiz.questions[idx].correctIndex) {
          correct += 1;
        }
      }
      return correct;
    }

    function quizIsComplete() {
      return selectedAnswers.size === activeQuiz.questions.length;
    }

    function setAggregateState(correctCount) {
      clearAggregateState();
      if (correctCount === activeQuiz.questions.length) {
        quizCard.classList.add("quiz-state-all-correct");
      } else if (correctCount === 0) {
        quizCard.classList.add("quiz-state-none-correct");
      } else {
        quizCard.classList.add("quiz-state-some-correct");
      }
    }

    function renderQuiz() {
      const totalQuestions = activeQuiz.questions.length;
      const answeredCount = selectedAnswers.size;
      const complete = quizIsComplete();

      quizCard.dataset.quizId = activeQuiz.id;
      quizTitle.textContent = activeQuiz.title;
      quizProgress.textContent = `Answered ${answeredCount} of ${totalQuestions}`;
      quizQuestions.innerHTML = "";

      activeQuiz.questions.forEach((question, questionIndex) => {
        const questionNumber = questionIndex + 1;
        const selectedAnswer = selectedAnswers.get(questionIndex);
        const answered = Number.isInteger(selectedAnswer);
        const isCorrect = answered && selectedAnswer === question.correctIndex;

        const article = document.createElement("article");
        article.className = "quiz-question";
        article.setAttribute("data-testid", `quiz-question-${questionNumber}`);

        const heading = document.createElement("h3");
        heading.textContent = `Question ${questionNumber}: ${question.prompt}`;
        article.appendChild(heading);

        const optionsWrap = document.createElement("div");
        optionsWrap.className = "quiz-options";

        question.answers.forEach((answerText, answerIndex) => {
          const answerBtn = document.createElement("button");
          answerBtn.type = "button";
          answerBtn.className = "quiz-option";
          answerBtn.setAttribute(
            "data-testid",
            `quiz-q${questionNumber}-option-${answerIndex + 1}`
          );
          answerBtn.setAttribute(
            "data-quiz-correct",
            answerIndex === question.correctIndex ? "true" : "false"
          );
          answerBtn.textContent = `${String.fromCharCode(65 + answerIndex)}. ${answerText}`;

          if (answered) {
            answerBtn.disabled = true;
            if (answerIndex === selectedAnswer) {
              answerBtn.classList.add("is-selected");
            }
            if (answerIndex === question.correctIndex) {
              answerBtn.classList.add("is-correct-answer");
            }
          } else {
            answerBtn.addEventListener("click", () => {
              if (inTransition || selectedAnswers.has(questionIndex)) {
                return;
              }
              selectedAnswers.set(questionIndex, answerIndex);
              renderQuiz();
            });
          }
          optionsWrap.appendChild(answerBtn);
        });
        article.appendChild(optionsWrap);

        const questionResult = document.createElement("p");
        questionResult.className = "quiz-question-result";
        questionResult.setAttribute(
          "data-testid",
          `quiz-question-${questionNumber}-result`
        );
        if (answered) {
          questionResult.textContent = isCorrect ? "Correct" : "Incorrect";
          questionResult.classList.add(isCorrect ? "correct" : "incorrect");
        } else {
          questionResult.textContent = "Answer pending";
        }
        article.appendChild(questionResult);

        quizQuestions.appendChild(article);
      });

      if (complete) {
        const correctCount = countCorrectAnswers();
        const percent = Math.round((correctCount / totalQuestions) * 100);
        quizPercent.textContent = `${percent}% correct (${correctCount}/${totalQuestions})`;
        if (correctCount === totalQuestions) {
          quizOverallStatus.textContent = "Overall result: Green success state.";
        } else if (correctCount === 0) {
          quizOverallStatus.textContent = "Overall result: Red success state.";
        } else {
          quizOverallStatus.textContent = "Overall result: Orange success state.";
        }
        setAggregateState(correctCount);
        quizSummary.hidden = false;
        nextQuizButton.hidden = false;
      } else {
        clearAggregateState();
        quizSummary.hidden = true;
        nextQuizButton.hidden = true;
      }
    }

    nextQuizButton.addEventListener("click", () => {
      if (!quizIsComplete() || inTransition) {
        return;
      }
      inTransition = true;
      quizCard.classList.add("quiz-card-transition");
      if (transitionHandle !== null) {
        window.clearTimeout(transitionHandle);
      }
      transitionHandle = window.setTimeout(() => {
        const previousId = activeQuiz.id;
        activeQuiz = pickRandomQuiz(previousId);
        selectedAnswers = new Map();
        quizCard.classList.remove("quiz-card-transition");
        inTransition = false;
        renderQuiz();
      }, QUIZ_TRANSITION_MS);
    });

    renderQuiz();
  }

  ensureAccountsStore();

  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", (event) => {
      event.preventDefault();

      const usernameInput = document.getElementById("username");
      const passwordInput = document.getElementById("password");
      const error = document.getElementById("login-error");
      const username = normalizeUsername(usernameInput?.value || "");
      const password = passwordInput?.value || "";
      const accounts = ensureAccountsStore();
      const account = findAccountByUsername(accounts, username);

      if (account && account.password === password) {
        setError(error, null);
        localStorage.setItem(AUTH_USER_KEY, account.username);
        window.location.href = "home.html";
      } else {
        setError(error, "Invalid credentials.");
      }
    });
  }

  const registerForm = document.getElementById("register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", (event) => {
      event.preventDefault();

      const usernameInput = document.getElementById("register-username");
      const passwordInput = document.getElementById("register-password");
      const error = document.getElementById("register-error");
      const username = normalizeUsername(usernameInput?.value || "");
      const password = passwordInput?.value || "";
      const validationError = validateRegistration(username, password);
      if (validationError) {
        setError(error, validationError);
        return;
      }

      const accounts = ensureAccountsStore();
      if (findAccountByUsername(accounts, username)) {
        setError(error, "Username already exists.");
        return;
      }

      const updated = [...accounts, { username, password }];
      saveAccounts(updated);
      setError(error, null);
      localStorage.setItem(AUTH_USER_KEY, username);
      window.location.href = "home.html";
    });
  }

  const welcome = document.getElementById("welcome");
  if (welcome) {
    const username = requireAuthenticatedUser("home");
    if (!username) {
      return;
    }

    const userName = document.getElementById("user-name");
    if (userName) {
      const homeProfile = getSavedProfile(username);
      userName.textContent = homeProfile.displayName || username;
    }

    const logoutButton = document.getElementById("logout-button");
    logoutButton?.addEventListener("click", () => {
      localStorage.removeItem(AUTH_USER_KEY);
      window.location.href = "index.html";
    });

    initializeHomeQuiz();
    initializeFeed(username);
  }

  const profileRoot = document.getElementById("profile-root");
  if (profileRoot) {
    const username = requireAuthenticatedUser("profile");
    if (!username) {
      return;
    }

    const profileUsername = document.getElementById("profile-username");
    if (profileUsername) {
      profileUsername.textContent = `Username: ${username}`;
    }

    const aboutInput = document.getElementById("profile-about-input");
    const countrySelect = document.getElementById("profile-country-select");
    const stateContainer = document.getElementById("profile-state-container");
    const stateSelect = document.getElementById("profile-state-select");
    const displayNameInput = document.getElementById("profile-displayname-input");

    if (countrySelect instanceof HTMLSelectElement) {
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Select country";
      countrySelect.appendChild(placeholder);
      setSelectOptions(countrySelect, COUNTRY_OPTIONS);
    }

    if (stateSelect instanceof HTMLSelectElement) {
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Select state";
      stateSelect.appendChild(placeholder);
      setSelectOptions(stateSelect, US_STATE_OPTIONS);
    }

    if (aboutInput instanceof HTMLTextAreaElement) {
      aboutInput.maxLength = ABOUT_ME_MAX_LEN;
      aboutInput.value = getSavedAboutMe(username);
      aboutInput.addEventListener("input", () => {
        aboutInput.value = truncateAboutMe(aboutInput.value);
      });
    }

    const savedProfile = getSavedProfile(username);
    if (countrySelect instanceof HTMLSelectElement) {
      countrySelect.value = savedProfile.country;
    }
    if (stateSelect instanceof HTMLSelectElement) {
      stateSelect.value = savedProfile.state;
    }
    if (displayNameInput instanceof HTMLInputElement) {
      displayNameInput.value = savedProfile.displayName;
    }
    applyStateVisibility(countrySelect, stateContainer, stateSelect);

    const timezoneSelect = document.getElementById("profile-timezone-select");
    const birthdayInput = document.getElementById("profile-birthday-input");
    const hometownInput = document.getElementById("profile-hometown-input");
    const addressInput = document.getElementById("profile-address-input");
    const favoriteColorInput = document.getElementById("profile-favoritecolor-input");
    const occupationInput = document.getElementById("profile-occupation-input");
    const pronounsInput = document.getElementById("profile-pronouns-input");
    const favoriteQuoteInput = document.getElementById("profile-favoritequote-input");
    const socialLinkedinInput = document.getElementById("profile-social-linkedin-input");
    const socialXtwitterInput = document.getElementById("profile-social-xtwitter-input");
    const socialInstagramInput = document.getElementById("profile-social-instagram-input");
    const socialFacebookInput = document.getElementById("profile-social-facebook-input");
    const socialGithubInput = document.getElementById("profile-social-github-input");

    if (timezoneSelect instanceof HTMLSelectElement) {
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Select timezone";
      timezoneSelect.appendChild(placeholder);
      setSelectOptions(timezoneSelect, TIMEZONE_OPTIONS);
      timezoneSelect.value = savedProfile.timezone;
    }
    if (birthdayInput instanceof HTMLInputElement) {
      birthdayInput.value = savedProfile.birthday;
    }
    if (hometownInput instanceof HTMLInputElement) {
      hometownInput.value = savedProfile.hometown;
    }
    if (addressInput instanceof HTMLTextAreaElement) {
      addressInput.value = savedProfile.address;
    }
    if (favoriteColorInput instanceof HTMLInputElement) {
      favoriteColorInput.value = savedProfile.favoriteColor;
    }
    if (occupationInput instanceof HTMLInputElement) {
      occupationInput.value = savedProfile.occupation;
    }
    if (pronounsInput instanceof HTMLInputElement) {
      pronounsInput.value = savedProfile.pronouns;
    }
    if (favoriteQuoteInput instanceof HTMLTextAreaElement) {
      favoriteQuoteInput.value = savedProfile.favoriteQuote;
      favoriteQuoteInput.addEventListener("input", () => {
        favoriteQuoteInput.value = truncateFavoriteQuote(favoriteQuoteInput.value);
      });
    }
    if (socialLinkedinInput instanceof HTMLInputElement) {
      socialLinkedinInput.value = savedProfile.socialLinks.linkedin;
    }
    if (socialXtwitterInput instanceof HTMLInputElement) {
      socialXtwitterInput.value = savedProfile.socialLinks.xTwitter;
    }
    if (socialInstagramInput instanceof HTMLInputElement) {
      socialInstagramInput.value = savedProfile.socialLinks.instagram;
    }
    if (socialFacebookInput instanceof HTMLInputElement) {
      socialFacebookInput.value = savedProfile.socialLinks.facebook;
    }
    if (socialGithubInput instanceof HTMLInputElement) {
      socialGithubInput.value = savedProfile.socialLinks.github;
    }

    if (countrySelect instanceof HTMLSelectElement) {
      countrySelect.addEventListener("change", () => {
        applyStateVisibility(countrySelect, stateContainer, stateSelect);
      });
    }

    const saveButton = document.getElementById("profile-save-button");
    saveButton?.addEventListener("click", () => {
      if (!(aboutInput instanceof HTMLTextAreaElement)) {
        return;
      }
      aboutInput.value = truncateAboutMe(aboutInput.value);
      const country = countrySelect instanceof HTMLSelectElement ? countrySelect.value : "";
      const state = stateSelect instanceof HTMLSelectElement ? stateSelect.value : "";
      const displayName = displayNameInput instanceof HTMLInputElement
        ? normalizeDisplayName(displayNameInput.value)
        : "";
      if (displayNameInput instanceof HTMLInputElement) {
        displayNameInput.value = displayName;
      }
      const birthday = birthdayInput instanceof HTMLInputElement ? birthdayInput.value.trim() : "";
      const hometown = hometownInput instanceof HTMLInputElement ? hometownInput.value.trim() : "";
      const address = addressInput instanceof HTMLTextAreaElement ? addressInput.value.trim() : "";
      const timezone = timezoneSelect instanceof HTMLSelectElement ? timezoneSelect.value : "";
      const favoriteColor = favoriteColorInput instanceof HTMLInputElement
        ? favoriteColorInput.value.trim()
        : "";
      const occupation = occupationInput instanceof HTMLInputElement ? occupationInput.value.trim() : "";
      const pronouns = pronounsInput instanceof HTMLInputElement ? pronounsInput.value.trim() : "";
      const favoriteQuote = favoriteQuoteInput instanceof HTMLTextAreaElement
        ? truncateFavoriteQuote(favoriteQuoteInput.value)
        : "";
      if (favoriteQuoteInput instanceof HTMLTextAreaElement) {
        favoriteQuoteInput.value = favoriteQuote;
      }
      const socialLinks = {
        linkedin: socialLinkedinInput instanceof HTMLInputElement ? socialLinkedinInput.value.trim() : "",
        xTwitter: socialXtwitterInput instanceof HTMLInputElement ? socialXtwitterInput.value.trim() : "",
        instagram: socialInstagramInput instanceof HTMLInputElement ? socialInstagramInput.value.trim() : "",
        facebook: socialFacebookInput instanceof HTMLInputElement ? socialFacebookInput.value.trim() : "",
        github: socialGithubInput instanceof HTMLInputElement ? socialGithubInput.value.trim() : "",
      };
      setSavedProfile(username, {
        aboutMe: aboutInput.value,
        country,
        state,
        displayName,
        birthday,
        hometown,
        address,
        timezone,
        favoriteColor,
        occupation,
        pronouns,
        favoriteQuote,
        socialLinks,
      });
      applyStateVisibility(countrySelect, stateContainer, stateSelect);
    });
  }
})();
