// MathonGo JEE Papers PDF Bot - Cloudflare Workers
// Fetches all JEE Main PYQ papers and sends direct PDF links

const MATHONGO_BASE = "https://www.mathongo.com";
const MATHONGO_URL = "https://www.mathongo.com/iit-jee/jee-main-previous-year-question-paper";

export default {
  async fetch(request, env) {
    const BOT_TOKEN = env.BOT_TOKEN;
    const TELEGRAM_API = `https://api.telegram.org/bot${BOT_TOKEN}`;
    
    const url = new URL(request.url);
    
    try {
      // Webhook handler
      if (url.pathname === "/webhook" && request.method === "POST") {
        const update = await request.json();
        await handleUpdate(update, TELEGRAM_API, env);
        return new Response("OK", { status: 200 });
      }
      
      // Set webhook
      if (url.pathname === "/set-webhook") {
        const webhookUrl = `${url.origin}/webhook`;
        const response = await fetch(`${TELEGRAM_API}/setWebhook`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            url: webhookUrl,
            allowed_updates: ["message", "callback_query"]
          })
        });
        const result = await response.json();
        return new Response(JSON.stringify(result, null, 2), {
          headers: { "Content-Type": "application/json" }
        });
      }
      
      // Delete webhook
      if (url.pathname === "/delete-webhook") {
        const response = await fetch(`${TELEGRAM_API}/deleteWebhook`);
        const result = await response.json();
        return new Response(JSON.stringify(result, null, 2));
      }
      
      // Get bot info
      if (url.pathname === "/info") {
        const response = await fetch(`${TELEGRAM_API}/getMe`);
        const result = await response.json();
        return new Response(JSON.stringify(result, null, 2), {
          headers: { "Content-Type": "application/json" }
        });
      }
      
      // Test scraping
      if (url.pathname === "/test-scrape") {
        const papers = await scrapeMathonGo();
        return new Response(JSON.stringify(papers, null, 2), {
          headers: { "Content-Type": "application/json" }
        });
      }
      
      // Health check
      if (url.pathname === "/") {
        return new Response(`
          <!DOCTYPE html>
          <html>
          <head><title>MathonGo PDF Bot</title></head>
          <body style="font-family: Arial; padding: 20px; background: #1a1a2e; color: #eee;">
            <h1>🎓 MathonGo JEE Papers Bot</h1>
            <p>Status: ✅ Running</p>
            <h3>Endpoints:</h3>
            <ul>
              <li><a href="/set-webhook" style="color: #4fc3f7;">/set-webhook</a> - Setup bot webhook</li>
              <li><a href="/info" style="color: #4fc3f7;">/info</a> - Bot information</li>
              <li><a href="/test-scrape" style="color: #4fc3f7;">/test-scrape</a> - Test paper scraping</li>
            </ul>
          </body>
          </html>
        `, { headers: { "Content-Type": "text/html" } });
      }
      
      return new Response("Not Found", { status: 404 });
      
    } catch (error) {
      console.error("Error:", error);
      return new Response(`Error: ${error.message}`, { status: 500 });
    }
  }
};

// Handle Telegram updates
async function handleUpdate(update, TELEGRAM_API, env) {
  try {
    const message = update.message;
    const callbackQuery = update.callback_query;
    
    if (callbackQuery) {
      await handleCallback(callbackQuery, TELEGRAM_API);
      return;
    }
    
    if (!message?.text) return;
    
    const chatId = message.chat.id;
    const text = message.text.trim().toLowerCase();
    const firstName = message.from?.first_name || "Student";
    
    // Command handlers
    if (text === "/start") {
      await sendWelcome(TELEGRAM_API, chatId, firstName);
    }
    else if (text === "/papers" || text === "/getpapers") {
      await handleGetPapers(TELEGRAM_API, chatId);
    }
    else if (text === "/years") {
      await sendYearSelector(TELEGRAM_API, chatId);
    }
    else if (text.startsWith("/year_")) {
      const year = text.replace("/year_", "");
      await handleGetPapers(TELEGRAM_API, chatId, year);
    }
    else if (text === "/help") {
      await sendHelp(TELEGRAM_API, chatId);
    }
    else if (text === "/about") {
      await sendAbout(TELEGRAM_API, chatId);
    }
    else {
      await sendMessage(TELEGRAM_API, chatId, 
        "❓ Unknown command. Use /help to see available commands."
      );
    }
    
  } catch (error) {
    console.error("Update handling error:", error);
  }
}

// Handle callback queries (button presses)
async function handleCallback(callbackQuery, TELEGRAM_API) {
  const chatId = callbackQuery.message.chat.id;
  const messageId = callbackQuery.message.message_id;
  const data = callbackQuery.data;
  
  // Acknowledge the callback
  await fetch(`${TELEGRAM_API}/answerCallbackQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ 
      callback_query_id: callbackQuery.id,
      text: "Processing..."
    })
  });
  
  if (data === "get_all_papers") {
    await handleGetPapers(TELEGRAM_API, chatId);
  }
  else if (data === "select_year") {
    await sendYearSelector(TELEGRAM_API, chatId);
  }
  else if (data.startsWith("year_")) {
    const year = data.replace("year_", "");
    await handleGetPapers(TELEGRAM_API, chatId, year);
  }
  else if (data === "help") {
    await sendHelp(TELEGRAM_API, chatId);
  }
}

// Send welcome message
async function sendWelcome(TELEGRAM_API, chatId, name) {
  const keyboard = {
    inline_keyboard: [
      [{ text: "📚 Get All Papers", callback_data: "get_all_papers" }],
      [{ text: "📅 Select by Year", callback_data: "select_year" }],
      [{ text: "❓ Help", callback_data: "help" }]
    ]
  };
  
  await sendMessage(TELEGRAM_API, chatId,
    `🎓 *Welcome ${name}!*\n\n` +
    `I'm your *JEE Main PYQ Papers* bot!\n\n` +
    `I can fetch all Previous Year Question Papers from MathonGo and give you direct PDF download links.\n\n` +
    `*Features:*\n` +
    `📄 Direct PDF downloads\n` +
    `📅 Papers from 2015-2024\n` +
    `✅ Both Questions & Solutions\n` +
    `⚡ Fast & Easy access\n\n` +
    `Click a button below to get started! 👇`,
    { 
      parse_mode: "Markdown",
      reply_markup: JSON.stringify(keyboard)
    }
  );
}

// Send year selector
async function sendYearSelector(TELEGRAM_API, chatId) {
  const years = ["2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017", "2016", "2015"];
  
  const keyboard = {
    inline_keyboard: [
      [
        { text: "📅 2024", callback_data: "year_2024" },
        { text: "📅 2023", callback_data: "year_2023" }
      ],
      [
        { text: "📅 2022", callback_data: "year_2022" },
        { text: "📅 2021", callback_data: "year_2021" }
      ],
      [
        { text: "📅 2020", callback_data: "year_2020" },
        { text: "📅 2019", callback_data: "year_2019" }
      ],
      [
        { text: "📅 2018", callback_data: "year_2018" },
        { text: "📅 2017", callback_data: "year_2017" }
      ],
      [
        { text: "📅 2016", callback_data: "year_2016" },
        { text: "📅 2015", callback_data: "year_2015" }
      ],
      [{ text: "📚 All Papers", callback_data: "get_all_papers" }]
    ]
  };
  
  await sendMessage(TELEGRAM_API, chatId,
    `📅 *Select Year*\n\nChoose a year to get JEE Main papers:`,
    { 
      parse_mode: "Markdown",
      reply_markup: JSON.stringify(keyboard)
    }
  );
}

// Main function to get papers
async function handleGetPapers(TELEGRAM_API, chatId, filterYear = null) {
  const yearText = filterYear ? ` for ${filterYear}` : "";
  
  await sendMessage(TELEGRAM_API, chatId, 
    `🔄 *Fetching papers${yearText}...*\n\nPlease wait, this may take a few seconds.`,
    { parse_mode: "Markdown" }
  );
  
  try {
    const papers = await scrapeMathonGo(filterYear);
    
    if (!papers || papers.length === 0) {
      await sendMessage(TELEGRAM_API, chatId,
        `❌ *No papers found${yearText}*\n\n` +
        `This could be because:\n` +
        `• The website structure changed\n` +
        `• Network issues\n` +
        `• No papers available for this year\n\n` +
        `Try /papers to get all papers.`,
        { parse_mode: "Markdown" }
      );
      return;
    }
    
    // Send summary
    await sendMessage(TELEGRAM_API, chatId,
      `✅ *Found ${papers.length} papers${yearText}!*\n\n` +
      `Sending download links...`,
      { parse_mode: "Markdown" }
    );
    
    // Group papers by year
    const groupedPapers = groupByYear(papers);
    
    // Send papers grouped by year
    for (const [year, yearPapers] of Object.entries(groupedPapers)) {
      let message = `📅 *JEE Main ${year}*\n\n`;
      
      yearPapers.forEach((paper, idx) => {
        const icon = paper.type === "solution" ? "📝" : "📄";
        message += `${icon} *${paper.name}*\n`;
        message += `🔗 [Download PDF](${paper.directUrl})\n\n`;
      });
      
      await sendMessage(TELEGRAM_API, chatId, message, {
        parse_mode: "Markdown",
        disable_web_page_preview: true
      });
      
      // Small delay to avoid rate limiting
      await sleep(300);
    }
    
    // Final message
    await sendMessage(TELEGRAM_API, chatId,
      `✅ *All papers sent!*\n\n` +
      `💡 *Tips:*\n` +
      `• Click the links to download PDFs directly\n` +
      `• Use /years to filter by specific year\n` +
      `• Papers include both Questions & Solutions\n\n` +
      `📚 Good luck with your preparation! 🎯`,
      { parse_mode: "Markdown" }
    );
    
  } catch (error) {
    console.error("Scraping error:", error);
    await sendMessage(TELEGRAM_API, chatId,
      `❌ *Error fetching papers*\n\n` +
      `Error: ${error.message}\n\n` +
      `Please try again later or contact support.`,
      { parse_mode: "Markdown" }
    );
  }
}

// Scrape MathonGo website
async function scrapeMathonGo(filterYear = null) {
  const papers = [];
  
  // Fetch main page
  const response = await fetch(MATHONGO_URL, {
    headers: {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.5",
      "Referer": "https://www.google.com/",
      "DNT": "1"
    }
  });
  
  if (!response.ok) {
    throw new Error(`Failed to fetch MathonGo: ${response.status} ${response.statusText}`);
  }
  
  const html = await response.text();
  
  // Extract all links and paper information
  const extractedPapers = extractPapersFromHTML(html);
  
  // Filter by year if specified
  for (const paper of extractedPapers) {
    if (filterYear) {
      if (paper.year === filterYear || paper.name.includes(filterYear)) {
        papers.push(paper);
      }
    } else {
      papers.push(paper);
    }
  }
  
  return papers;
}

// Extract paper links from HTML
function extractPapersFromHTML(html) {
  const papers = [];
  const seenUrls = new Set();
  
  // Pattern 1: Google Drive links
  const drivePattern = /href=["'](https:\/\/drive\.google\.com\/[^"']+)["'][^>]*>([^<]*)/gi;
  let match;
  
  while ((match = drivePattern.exec(html)) !== null) {
    const url = match[1];
    const name = cleanName(match[2]);
    
    if (!seenUrls.has(url) && name) {
      seenUrls.add(url);
      papers.push(createPaperObject(url, name));
    }
  }
  
  // Pattern 2: Direct PDF links
  const pdfPattern = /href=["'](https?:\/\/[^"']+\.pdf[^"']*)["'][^>]*>([^<]*)/gi;
  
  while ((match = pdfPattern.exec(html)) !== null) {
    const url = match[1];
    const name = cleanName(match[2]);
    
    if (!seenUrls.has(url) && name) {
      seenUrls.add(url);
      papers.push(createPaperObject(url, name));
    }
  }
  
  // Pattern 3: MathonGo CDN/storage links
  const cdnPattern = /href=["'](https?:\/\/[^"']*(?:cdn|storage|assets)[^"']*\.pdf[^"']*)["']/gi;
  
  while ((match = cdnPattern.exec(html)) !== null) {
    const url = match[1];
    if (!seenUrls.has(url)) {
      seenUrls.add(url);
      papers.push(createPaperObject(url, extractNameFromUrl(url)));
    }
  }
  
  // Pattern 4: Links with download attribute
  const downloadPattern = /<a[^>]+href=["']([^"']+)["'][^>]*download[^>]*>([^<]*)/gi;
  
  while ((match = downloadPattern.exec(html)) !== null) {
    const url = match[1].startsWith("http") ? match[1] : MATHONGO_BASE + match[1];
    const name = cleanName(match[2]);
    
    if (!seenUrls.has(url) && name) {
      seenUrls.add(url);
      papers.push(createPaperObject(url, name));
    }
  }
  
  // Pattern 5: Data attributes (many sites store URLs in data-*)
  const dataPattern = /data-(?:url|href|pdf|link)=["']([^"']+\.pdf[^"']*)["']/gi;
  
  while ((match = dataPattern.exec(html)) !== null) {
    const url = match[1].startsWith("http") ? match[1] : MATHONGO_BASE + match[1];
    if (!seenUrls.has(url)) {
      seenUrls.add(url);
      papers.push(createPaperObject(url, extractNameFromUrl(url)));
    }
  }
  
  // Pattern 6: JSON embedded data
  const jsonPatterns = [
    /"url"\s*:\s*"([^"]+\.pdf[^"]*)"/gi,
    /"pdf(?:Url|Link)?"\s*:\s*"([^"]+)"/gi,
    /"download(?:Url|Link)?"\s*:\s*"([^"]+)"/gi
  ];
  
  for (const pattern of jsonPatterns) {
    while ((match = pattern.exec(html)) !== null) {
      let url = match[1].replace(/\\/g, "");
      if (!url.startsWith("http")) url = MATHONGO_BASE + url;
      
      if (!seenUrls.has(url)) {
        seenUrls.add(url);
        papers.push(createPaperObject(url, extractNameFromUrl(url)));
      }
    }
  }
  
  // Pattern 7: Look for paper listings in common structures
  const listingPattern = /<(?:div|li|a)[^>]*class=["'][^"']*(?:paper|download|pdf)[^"']*["'][^>]*>[\s\S]*?href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/(?:div|li|a)>/gi;
  
  while ((match = listingPattern.exec(html)) !== null) {
    let url = match[1];
    if (!url.startsWith("http")) url = MATHONGO_BASE + url;
    const name = cleanName(match[2].replace(/<[^>]+>/g, ""));
    
    if (!seenUrls.has(url) && name && (url.includes("pdf") || url.includes("drive"))) {
      seenUrls.add(url);
      papers.push(createPaperObject(url, name));
    }
  }
  
  // If no papers found, try to find any relevant links
  if (papers.length === 0) {
    const anyLinkPattern = /<a[^>]+href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
    
    while ((match = anyLinkPattern.exec(html)) !== null) {
      const url = match[1];
      const text = match[2].replace(/<[^>]+>/g, "").trim().toLowerCase();
      
      // Check if link text suggests it's a paper
      if ((text.includes("paper") || text.includes("question") || 
           text.includes("solution") || text.includes("download") ||
           text.includes("pdf") || text.includes("pyq")) &&
          !seenUrls.has(url)) {
        
        let fullUrl = url.startsWith("http") ? url : MATHONGO_BASE + url;
        seenUrls.add(url);
        papers.push(createPaperObject(fullUrl, cleanName(match[2].replace(/<[^>]+>/g, ""))));
      }
    }
  }
  
  return papers;
}

// Create paper object with processed URLs
function createPaperObject(url, name) {
  const year = extractYear(name) || extractYear(url) || "Other";
  const type = detectPaperType(name, url);
  const directUrl = convertToDirectDownload(url);
  
  return {
    name: name || "JEE Paper",
    url: url,
    directUrl: directUrl,
    year: year,
    type: type
  };
}

// Convert various sharing links to direct download
function convertToDirectDownload(url) {
  // Google Drive
  if (url.includes("drive.google.com")) {
    // Extract file ID from various formats
    let fileId = null;
    
    // Format: /file/d/FILE_ID/
    const fileMatch = url.match(/\/file\/d\/([a-zA-Z0-9_-]+)/);
    if (fileMatch) fileId = fileMatch[1];
    
    // Format: ?id=FILE_ID or &id=FILE_ID
    const idMatch = url.match(/[?&]id=([a-zA-Z0-9_-]+)/);
    if (idMatch) fileId = idMatch[1];
    
    // Format: /open?id=FILE_ID
    const openMatch = url.match(/\/open\?id=([a-zA-Z0-9_-]+)/);
    if (openMatch) fileId = openMatch[1];
    
    if (fileId) {
      return `https://drive.google.com/uc?export=download&id=${fileId}`;
    }
  }
  
  // Dropbox
  if (url.includes("dropbox.com")) {
    return url.replace(/dl=0/, "dl=1").replace(/\?dl=0/, "?dl=1");
  }
  
  // OneDrive
  if (url.includes("1drv.ms") || url.includes("onedrive")) {
    return url.replace(/redir/, "download");
  }
  
  return url;
}

// Extract year from text
function extractYear(text) {
  if (!text) return null;
  const yearMatch = text.match(/20[1-2][0-9]/);
  return yearMatch ? yearMatch[0] : null;
}

// Detect if paper is question or solution
function detectPaperType(name, url) {
  const text = (name + " " + url).toLowerCase();
  if (text.includes("solution") || text.includes("answer") || text.includes("key")) {
    return "solution";
  }
  return "question";
}

// Clean paper name
function cleanName(name) {
  if (!name) return "";
  return name
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// Extract name from URL
function extractNameFromUrl(url) {
  try {
    const parts = url.split("/");
    let filename = parts[parts.length - 1] || parts[parts.length - 2] || "";
    filename = filename.split("?")[0];
    filename = decodeURIComponent(filename);
    filename = filename.replace(/[_-]/g, " ").replace(/\.pdf$/i, "");
    return filename || "JEE Paper";
  } catch (e) {
    return "JEE Paper";
  }
}

// Group papers by year
function groupByYear(papers) {
  const grouped = {};
  
  papers.forEach(paper => {
    const year = paper.year || "Other";
    if (!grouped[year]) {
      grouped[year] = [];
    }
    grouped[year].push(paper);
  });
  
  // Sort years in descending order
  const sorted = {};
  Object.keys(grouped)
    .sort((a, b) => b.localeCompare(a))
    .forEach(key => {
      sorted[key] = grouped[key];
    });
  
  return sorted;
}

// Send help message
async function sendHelp(TELEGRAM_API, chatId) {
  await sendMessage(TELEGRAM_API, chatId,
    `📖 *Help & Commands*\n\n` +
    `*Available Commands:*\n` +
    `/start - Start the bot\n` +
    `/papers - Get all JEE Main papers\n` +
    `/years - Select papers by year\n` +
    `/help - Show this help message\n` +
    `/about - About this bot\n\n` +
    `*How to use:*\n` +
    `1. Send /papers to get all papers\n` +
    `2. Or use /years to select a specific year\n` +
    `3. Click on download links to get PDFs\n\n` +
    `*Note:*\n` +
    `• PDFs are fetched from MathonGo\n` +
    `• Some links redirect to Google Drive\n` +
    `• If a link doesn't work, try again later`,
    { parse_mode: "Markdown" }
  );
}

// Send about message
async function sendAbout(TELEGRAM_API, chatId) {
  await sendMessage(TELEGRAM_API, chatId,
    `ℹ️ *About This Bot*\n\n` +
    `*MathonGo JEE Papers Bot*\n` +
    `Version: 1.0.0\n\n` +
    `This bot fetches JEE Main Previous Year Question Papers from MathonGo and provides direct download links.\n\n` +
    `*Features:*\n` +
    `• Papers from 2015-2024\n` +
    `• Question Papers & Solutions\n` +
    `• Direct PDF downloads\n` +
    `• Google Drive link conversion\n\n` +
    `Made with ❤️ for JEE Aspirants`,
    { parse_mode: "Markdown" }
  );
}

// Send message helper
async function sendMessage(TELEGRAM_API, chatId, text, options = {}) {
  const body = {
    chat_id: chatId,
    text: text,
    ...options
  };
  
  const response = await fetch(`${TELEGRAM_API}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  
  return response.json();
}

// Sleep helper
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
