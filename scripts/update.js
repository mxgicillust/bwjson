const fs = require('fs');
const fetch = require('node-fetch');

const fetchISBN = async () => {
    try {
        const response = await fetch(`https://raw.githubusercontent.com/mxgicillust/bwjson/main/isbn.json?t=${Date.now()}`);
        if (!response.ok) {
            console.error('Error fetching ISBN list:', response.statusText);
            return [];
        }
        return await response.json();
    } catch (error) {
        console.error('Error loading ISBN list:', error);
        return [];
    }
};

const fetchRakutenData = async (isbn) => {
    try {
        const response = await fetch(`https://api.mxgic007.workers.dev/?isbn=${isbn}`);
        
        if (!response.ok) {
            console.error(`Error fetching ISBN ${isbn}:`, response.statusText);
            return null;
        }

        const data = await response.json();
        const book = data?.Items?.[0]?.Item;

        if (!book) {
            console.warn(`No valid book data, ISBN: ${isbn}`);
            return null;
        }

        const releaseDateMatch = book.salesDate?.match(/(\d{4})年(\d{2})月(\d{2})日/);
        const releaseDate = releaseDateMatch
            ? `${releaseDateMatch[1]}-${releaseDateMatch[2]}-${releaseDateMatch[3]}`
            : null;

        return {
            isbn,
            title: book.title || "No Title",
            publisher: book.seriesName || "Unknown Publisher",
            releaseDate,
        };
    } catch (error) {
        console.error(`Error fetching ISBN ${isbn}:`, error.message);
        return null;
    }
};

const updateCache = async () => {
    console.log('Fetching ISBN list...');
    const isbnList = await fetchISBN();

    if (!isbnList || !Array.isArray(isbnList) || isbnList.length === 0) {
        console.error('No ISBNs to process. Exiting.');
        return;
    }

    console.log('Fetching data for ISBNs...');
    const cache = {};

    for (const isbn of isbnList) {
        console.log(`Fetching data for ISBN: ${isbn}`);
        const data = await fetchRakutenData(isbn);
        if (data) {
            cache[isbn] = data;
        }
    }

    const jsonFilePath = './data.json';
    fs.writeFileSync(jsonFilePath, JSON.stringify(cache, null, 2), 'utf8');
    console.log(`Cache updated successfully: ${jsonFilePath}`);
};

// Run the update
updateCache();
