'use strict';
const fs = require('fs');
const request = require('request');
const app = require('express')();

const port = 9979;
const rdfServerUrl = process.env.SOPHOX_URL;

app.use(function (req, res, next) {
	res.header('Access-Control-Allow-Origin', '*');
	res.header('Access-Control-Allow-Methods', 'PUT,DELETE,OPTIONS');
	res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, Content-Length, X-Requested-With');
	next();
});

app.options("/*", function (req, res) {
	res.sendStatus(200);
});

app.use(require('express-accesstoken-validation')({
	validationUri: 'https://www.openstreetmap.org/oauth/authorize',
	// validationUri: 'https://master.apis.dev.openstreetmap.org/oauth/authorize',
	tokenParam: 'oauth_token'
}));

app.use(require('body-parser').urlencoded({extended: true}));
app.put('/store/v1/:taskId/:osmType/:osmId/:selection', handleRequest);
app.delete('/store/v1/:taskId/:osmType/:osmId', handleRequest);

app.listen(port, (err) => {
	if (err) {
		console.error(err);
	} else {
		console.log(`server is listening on ${port}`);
	}
});


class MyError extends Error {
	constructor(code, msg) {
		super();
		this.code = code;
		this.msg = msg;
	}
}

async function handleRequest(req, resp) {
	try {
		const isDelete = req.method === 'DELETE';
		if (!isDelete && req.method !== 'PUT') {
			throw new MyError(500, 'Unknown method');
		}

		const taskId = parseTaskId(req);
		const osmType = parseOsmType(req);
		const osmId = parseOsmId(req);
		const selection = isDelete ? false : parseSelection(req);
		const userName = parseUserInfo(req);

		const logValues = [new Date().toISOString(), userName, taskId, `${osmType}/${osmId}`, req.method];
		if (selection) logValues.push(selection);
		const logStr = logValues.join('\t');
		console.log(logStr);
		fs.appendFile('vote-log.txt', logStr, function (err) {
			if (err) console.error(err);
		});

		const sparql = isDelete
			? sparqlDeleteVote(taskId, osmType, osmId, userName)
			: sparqlPutVote(taskId, osmType, osmId, userName, selection);

		await postToServer(sparql);

		resp.status(201).send('OK');

	} catch (err) {
		if (err instanceof MyError) {
			resp.status(err.code).send(err.msg);
		} else {
			resp.status(500).send('boom');
		}
		try {
			if (err instanceof MyError) {
				console.error(err.msg, JSON.stringify(req.params), JSON.stringify(req.body));
			} else {
				console.error(err, JSON.stringify(req.params), JSON.stringify(req.body));
			}
		} catch (e2) {
			console.error(err);
		}
	}
}

function parseTaskId(req) {
	// May contain letters, numbers anywhere, and -:_ symbols anywhere except first and last position
	// Matches osmutils.py - reSimpleLocalName
	const taskId = req.params.taskId;
	if (!/^[0-9a-zA-Z_]([-:0-9a-zA-Z_]{0,30}[0-9a-zA-Z_])?$/.test(taskId)) {
		throw new MyError(400, 'bad taskId');
	}
	return taskId;
}

function parseOsmType(req) {
	const osmType = req.params.osmType;
	if (!['node', 'way', 'relation'].includes(osmType)) {
		throw new MyError(400, 'bad osmType');
	}
	return osmType;
}

function parseOsmId(req) {
	const osmId = req.params.osmId;
	if (!/^[0-9]{1,16}$/.test(osmId) || osmId === '0') {
		throw new MyError(400, 'bad osmId');
	}
	return osmId;
}

function parseSelection(req) {
	const selection = req.params.selection;
	if (!/^(yes|no|[a-z])$/.test(selection)) {
		throw new MyError(400, 'bad selection');
	}
	return selection;
}

function parseUserInfo(req) {
	const {userId, userName} = req.body;
	if (!/^\d{1,15}$/.test(userId) || userId === '0') {
		throw new MyError(400, 'bad userId');
	}
	return userName;
}

function postToServer(sparql) {
	return new Promise((accept, reject) => {
		request.post({
			url: rdfServerUrl,
			form: {update: sparql}
		}, function (error, rdfResponse) {
			if (error) {
				return reject(error);
			}
			if (rdfResponse.statusCode !== 200) {
				console.error('statusCode:', rdfResponse && rdfResponse.statusCode);
				return reject(new Error(rdfResponse.body));
			}
			accept();
		});
	});
}

function sparqlPutVote(taskId, osmType, osmId, userName, selection) {
	const prefixes = [
		'prefix osmnode: <https://www.openstreetmap.org/node/>',
		'prefix osmway: <https://www.openstreetmap.org/way/>',
		'prefix osmrel: <https://www.openstreetmap.org/relation/>',
		'prefix osmm: <https://www.openstreetmap.org/meta/>'
	];

	const userURI = `<https://www.openstreetmap.org/user/${encodeURIComponent(userName)}>`;
	const taskURI = `<https://www.openstreetmap.org/task/${taskId}/${osmType}/${osmId}>`;
	const sparqlOsmId = `osm${osmType === 'relation' ? 'rel' : osmType}:${osmId}`;

	const statements = [
		`${sparqlOsmId} osmm:task ${taskURI} .`,
		`${taskURI} osmm:taskId "${taskId}" .`,
		`${taskURI} ${userURI} osmm:pick_${selection} .`,
		`${taskURI} ${userURI} "${(new Date()).toISOString()}"^^xsd:dateTime .`
	];

	return `${prefixes.join('\n')}` +
		`INSERT { ${statements.join('\n')} } WHERE {};`;
}

function sparqlDeleteVote(taskId, osmType, osmId, userName) {
	const userURI = `<https://www.openstreetmap.org/user/${encodeURIComponent(userName)}>`;
	const taskURI = `<https://www.openstreetmap.org/task/${taskId}/${osmType}/${osmId}>`;

	return `DELETE { ${taskURI} ${userURI} ?o } WHERE { ${taskURI} ${userURI} ?o . };`
}
